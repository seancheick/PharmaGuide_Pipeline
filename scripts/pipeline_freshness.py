"""Content fingerprints for pipeline inputs that must trigger regeneration.

Every stage manifest (clean, enrich, score) records two input fingerprints:
the reference data in scripts/data, and the code that ran the stage (its entry
script, every scripts/ module it imports, and its JSON config). The release
preflight compares both with the current checkout, so output built from older
data, older code, or a mix of revisions cannot pass as current.
"""

from __future__ import annotations

import argparse
import ast
import hashlib
import json
import sys
from pathlib import Path
from typing import Callable, Iterable

from stage_manifest import MANIFEST_NAME


REFERENCE_FINGERPRINT_KEY = "reference_data_sha256_v1"
CODE_FINGERPRINT_KEY = "stage_code_sha256_v1"
DATA_FINGERPRINT_KEY = "stage_data_sha256_v1"

#: Per stage: the script run_pipeline runs, the JSON config it reads outside
#: scripts/data (relative to scripts/), and its outputs (relative to
#: scripts/products). The stage manifest sits beside the outputs.
STAGES = {
    "clean": {
        "entry": "clean_dsld_data.py",
        "configs": ("config/cleaning_config.json",),
        "outputs": (
            "output_*/cleaned/cleaned_batch_*.json",
            "output_*/cleaned/cleaned_batch_*.jsonl",
        ),
    },
    "enrich": {
        "entry": "enrich_supplements_v3.py",
        "configs": ("config/enrichment_config.json",),
        "outputs": ("output_*_enriched/enriched/*.json",),
    },
    "score": {
        "entry": "score_products_v4.py",
        "configs": ("scoring_v4/config/*.json",),
        "outputs": ("output_*_scored/scored/*.json",),
    },
}
#: What to rerun when a stage's output is stale: that stage and every later one.
RERUN_STAGES = {"clean": "clean,enrich,score", "enrich": "enrich,score", "score": "score"}


def _reference_data_files(repo_root: Path) -> list[Path]:
    data_dir = Path(repo_root).resolve() / "scripts" / "data"
    return sorted(
        {
            # Operational identifier-audit cache, not an input to any stage.
            *(path for path in data_dir.glob("*.json") if path.name != "fda_unii_cache.json"),
            *(data_dir / "curated_overrides").glob("*.json"),
        },
        key=lambda path: path.relative_to(repo_root).as_posix(),
    )


def _bytes_digest(path: Path) -> bytes:
    file_digest = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(1024 * 1024):
            file_digest.update(chunk)
    return file_digest.digest()


def _content_set_fingerprint(
    paths: Iterable[Path],
    *,
    root: Path,
    file_digest: Callable[[Path], bytes] = _bytes_digest,
) -> str:
    """Hash relative paths and contents so touches do not look like changes."""
    root = Path(root).resolve()
    digest = hashlib.sha256()
    for path in sorted(
        {Path(path).resolve() for path in paths},
        key=lambda item: item.relative_to(root).as_posix(),
    ):
        relative = path.relative_to(root).as_posix().encode("utf-8")
        digest.update(len(relative).to_bytes(8, "big"))
        digest.update(relative)
        # Fixed-width digest marks the file boundary unambiguously.
        digest.update(file_digest(path))
    return digest.hexdigest()


def stage_data_fingerprint(paths: Iterable[Path], *,
                           content_hashes: dict[Path, bytes] | None = None) -> str:
    """Bind the actual flat input file inventory and full bytes, never mtimes."""
    paths = [Path(path).resolve() for path in paths]
    parents = {path.parent for path in paths}
    if len(parents) > 1:
        raise ValueError("Stage inputs must share one directory")
    # Only invocation-local hashes emitted by ownership verification belong here.
    # Never retain this map across a stage, verification or publication boundary.
    def digest(path: Path) -> bytes:
        if content_hashes is not None and path in content_hashes:
            return content_hashes[path]
        return _bytes_digest(path)
    return _content_set_fingerprint(paths, root=next(iter(parents), Path.cwd()),
                                    file_digest=digest)


def stage_data_files(directory: Path) -> list[Path]:
    """Stage data excludes manifests and other hidden operational files."""
    return sorted(path for pattern in ("*.json", "*.jsonl")
                  for path in Path(directory).glob(pattern)
                  if path.is_file() and not path.name.startswith("."))


def reference_data_fingerprint(repo_root: Path) -> str:
    """Return the deterministic stamp of the reference data every stage reads."""
    repo_root = Path(repo_root).resolve()
    return _content_set_fingerprint(
        _reference_data_files(repo_root),
        root=repo_root,
    )


#: path -> ((size, mtime_ns), digest, imports). A stage checks its code before
#: and after it runs; the second check re-parses only files that changed.
_PARSED: dict[Path, tuple[tuple[int, int], bytes, tuple]] = {}


def _parse_module(path: Path) -> tuple[bytes, tuple]:
    """Digest of a module's syntax tree without docstrings, and its imports.

    Comments and layout never reach the tree, and docstrings are dropped, so a
    documentation edit does not make every product stale.
    """
    stat = path.stat()
    key = (stat.st_size, stat.st_mtime_ns)
    cached = _PARSED.get(path)
    if cached is not None and cached[0] == key:
        return cached[1], cached[2]
    tree = ast.parse(path.read_bytes(), filename=str(path))
    imports = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imports.extend((0, alias.name, ()) for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            names = tuple(alias.name for alias in node.names)
            imports.append((node.level, node.module or "", names))
    for node in ast.walk(tree):
        if isinstance(
            node, (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)
        ) and ast.get_docstring(node, clean=False) is not None:
            del node.body[0]
    digest = hashlib.sha256(ast.dump(tree).encode("utf-8")).digest()
    _PARSED[path] = (key, digest, tuple(imports))
    return digest, tuple(imports)


def _imported_modules(scripts: Path, path: Path) -> set[Path]:
    """The scripts/ files a module imports; third-party and stdlib are skipped."""
    parts = list(path.relative_to(scripts).with_suffix("").parts)
    package = parts[:-1]
    names: set[str] = set()
    for level, module, imported in _parse_module(path)[1]:
        base = package[: len(package) - level + 1] if level else []
        dotted = ".".join(base + ([module] if module else []))
        if dotted:
            names.add(dotted)
            names.update(f"{dotted}.{name}" for name in imported)
    found = set()
    for name in names:
        pieces = name.split(".")
        # Importing a.b.c also runs a/__init__.py and a/b/__init__.py.
        for end in range(1, len(pieces) + 1):
            base = scripts.joinpath(*pieces[:end])
            for candidate in (base.with_suffix(".py"), base / "__init__.py"):
                if candidate.is_file():
                    found.add(candidate)
    return found


def stage_code_files(repo_root: Path, stage: str) -> list[Path]:
    """The files besides reference data whose content decides a stage's output."""
    scripts = Path(repo_root).resolve() / "scripts"
    spec = STAGES[stage]
    entry = scripts / spec["entry"]
    if not entry.is_file():
        raise ValueError(f"{stage} stage script is missing: {entry}")
    seen: set[Path] = set()
    todo = [entry]
    while todo:
        path = todo.pop()
        if path not in seen:
            seen.add(path)
            todo.extend(_imported_modules(scripts, path) - seen)
    for pattern in spec["configs"]:
        seen.update(path for path in scripts.glob(pattern) if path.is_file())
    return sorted(seen)


def _code_digest(path: Path) -> bytes:
    return _parse_module(path)[0] if path.suffix == ".py" else _bytes_digest(path)


def stage_code_fingerprint(repo_root: Path, stage: str) -> str:
    """Return the deterministic stamp of the code and config one stage runs."""
    repo_root = Path(repo_root).resolve()
    return _content_set_fingerprint(
        stage_code_files(repo_root, stage),
        root=repo_root,
        file_digest=_code_digest,
    )


def stage_input_fingerprints(repo_root: Path, stage: str) -> dict[str, str]:
    """What a stage manifest records: the reference data and the stage's code."""
    return {
        REFERENCE_FINGERPRINT_KEY: reference_data_fingerprint(repo_root),
        CODE_FINGERPRINT_KEY: stage_code_fingerprint(repo_root, stage),
    }


def _manifest_issue(manifest_path: Path, expected: dict[str, str]) -> str | None:
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        return f"{manifest_path}: unreadable ({exc})"

    if not isinstance(manifest, dict):
        return f"{manifest_path}: malformed manifest root"
    input_fingerprints = manifest.get("input_fingerprints")
    if input_fingerprints is not None and not isinstance(
        input_fingerprints, dict
    ):
        return f"{manifest_path}: malformed input_fingerprints"

    reasons = []
    for key, label in (
        (REFERENCE_FINGERPRINT_KEY, "reference_data"),
        (CODE_FINGERPRINT_KEY, "stage code"),
    ):
        declared = (input_fingerprints or {}).get(key)
        if declared != expected[key]:
            reason = "missing" if declared is None else "content mismatch"
            reasons.append(f"{label} fingerprint {reason}")
    return f"{manifest_path}: {'; '.join(reasons)}" if reasons else None


def stage_manifest_issue(
    repo_root: Path,
    manifest_path: Path,
    stage: str,
    *,
    raw_input_dir: Path | None = None,
) -> str | None:
    """Explain why one stage manifest is stale, or return None if current."""
    issue = _manifest_issue(
        Path(manifest_path).resolve(),
        stage_input_fingerprints(Path(repo_root).resolve(), stage),
    )
    if issue or raw_input_dir is None:
        return issue
    raw_input_dir = Path(raw_input_dir)
    if not raw_input_dir.is_dir():
        return f"{raw_input_dir}: missing raw input directory"
    stamp = Path(manifest_path).stat().st_mtime_ns
    newer = next((path for path in sorted(raw_input_dir.glob('*.json'))
                  if path.is_file() and path.stat().st_mtime_ns > stamp), None)
    return f"{manifest_path}: raw input newer than stage manifest: {newer}" if newer else None


def reusable_stage_issue(repo_root: Path, stage_dir: Path, stage: str,
                         input_dir: Path) -> str | None:
    """Require complete output ownership and current input bytes before reuse."""
    from stage_manifest import StageManifestError, select_stage_input_files

    try:
        issue = stage_manifest_issue(repo_root, stage_dir / MANIFEST_NAME, stage)
        if issue:
            return issue
        outputs = select_stage_input_files(
            stage_dir, stage, require_manifest=True, patterns=("*.json", "*.jsonl"))
        if not outputs:
            return "stage owns no outputs"
        if not input_dir.is_dir():
            return "missing stage input directory"
        inputs = stage_data_files(input_dir)
        if not inputs:
            return "stage has no inputs"
        manifest = json.loads((stage_dir / MANIFEST_NAME).read_text())
        if manifest.get("input_fingerprints", {}).get(DATA_FINGERPRINT_KEY) != stage_data_fingerprint(inputs):
            return "stage input inventory or content changed"
    except (StageManifestError, OSError, ValueError) as exc:
        return str(exc)
    return None


def dataset_resume_plan(repo_root: Path, raw_dir: Path,
                        output_prefix: Path) -> tuple[list[str], str]:
    """Reuse a verified prefix, rebuilding the first stale stage and successors."""
    prefix = str(output_prefix)
    directories = [Path(prefix) / "cleaned", Path(prefix + "_enriched") / "enriched",
                   Path(prefix + "_scored") / "scored"]
    stages = list(STAGES)
    inputs = Path(raw_dir)
    for index, (stage, directory) in enumerate(zip(stages, directories)):
        issue = reusable_stage_issue(repo_root, directory, stage, inputs)
        if issue:
            return stages[index:], issue
        inputs = directory
    return [], "all stage outputs and inputs verified"


def batch_source_fingerprint(repo_root: Path, raw_roots: Iterable[Path] = ()) -> str:
    """Freeze runtime source across brands, independently of generated outputs."""
    root = Path(repo_root).resolve()
    scripts = root / 'scripts'
    paths = set(_reference_data_files(root))
    paths.update(scripts.glob('*.py'))
    paths.update(scripts.glob('*.sh'))
    paths.update(root.glob('*.sh'))
    paths.update(path for pattern in ('.env', '.python-version', 'requirements*.txt',
                                      'scripts/audits/run_verification_gate.py')
                 for path in root.glob(pattern) if path.is_file())
    for directory in ('scoring_v4', 'config', 'contracts'):
        paths.update(path for path in (scripts / directory).rglob('*')
                     if path.is_file() and path.suffix in ('.py', '.json', '.sh'))
    # Freeze every runtime module, including dynamic imports, without reparsing
    # all ASTs between brands. Product-stage fingerprints remain semantic ASTs.
    excluded = {'products', 'dist', 'final_db_output', 'reports', 'tests', 'audits',
                '__pycache__', '.cache', '.venv', 'venv', 'data'}
    for directory in scripts.iterdir():
        if directory.is_dir() and directory.name not in excluded:
            paths.update(path for pattern in ('*.py', '*.sh')
                         for path in directory.rglob(pattern) if path.is_file())
    internal = {path for path in paths if path.resolve().is_relative_to(root)}
    external = sorted((path.relative_to(root).as_posix(), _bytes_digest(path).hex())
                      for path in paths - internal)
    source = _content_set_fingerprint(internal, root=root)
    inputs = [(str(Path(raw).resolve()), _content_set_fingerprint(
        Path(raw).rglob('*.json'), root=Path(raw).resolve())) for raw in raw_roots]
    return hashlib.sha256(json.dumps([source, external, inputs], sort_keys=True).encode()).hexdigest()


def stage_freshness_issues(repo_root: Path) -> list[str]:
    """Stage outputs whose reference data or stage code differs from now.

    Each issue starts with its stage name; rerun RERUN_STAGES of the earliest
    stale stage.
    """
    repo_root = Path(repo_root).resolve()
    products = repo_root / "scripts" / "products"
    reference = None
    issues: list[str] = []
    for stage, spec in STAGES.items():
        stage_dirs = sorted(
            {
                output.parent
                for pattern in spec["outputs"]
                for output in products.glob(pattern)
                if output.is_file() and not output.name.startswith(".")
            },
            key=str,
        )
        if not stage_dirs:
            continue
        if reference is None:
            reference = reference_data_fingerprint(repo_root)
        expected = {
            REFERENCE_FINGERPRINT_KEY: reference,
            CODE_FINGERPRINT_KEY: stage_code_fingerprint(repo_root, stage),
        }
        for stage_dir in stage_dirs:
            issue = _manifest_issue(stage_dir / MANIFEST_NAME, expected)
            if issue is not None:
                issues.append(f"{stage}: {issue}")
    return issues


def _main() -> int:
    parser = argparse.ArgumentParser(
        description="Check content-based pipeline freshness contracts."
    )
    subparsers = parser.add_subparsers(dest="command", required=True)
    baseline = subparsers.add_parser('batch-source-fingerprint')
    baseline.add_argument('--repo-root', type=Path, required=True)
    baseline.add_argument('--raw-inputs', type=Path, action='append', default=[])
    check = subparsers.add_parser(
        "check-stage-manifests",
        help=(
            "exit zero only when every given stage manifest matches the current "
            "reference data and stage code"
        ),
    )
    check.add_argument("--repo-root", type=Path, required=True)
    check.add_argument("--raw-inputs", type=Path,
                       help="Also reject a score manifest older than its raw submission labels")
    for stage in STAGES:
        check.add_argument(f"--{stage}", type=Path, metavar="MANIFEST")
    args = parser.parse_args()

    if args.command == 'batch-source-fingerprint':
        print(batch_source_fingerprint(args.repo_root, args.raw_inputs))
        return 0

    if args.command == "check-stage-manifests":
        checks = [
            (stage, getattr(args, stage))
            for stage in STAGES
            if getattr(args, stage) is not None
        ]
        if not checks:
            parser.error("name at least one stage manifest")
        if args.raw_inputs is not None and args.score is None:
            parser.error("--raw-inputs requires --score")
        issues = [
            issue
            for stage, manifest in checks
            if (issue := stage_manifest_issue(args.repo_root, manifest, stage,
                                             raw_input_dir=args.raw_inputs if stage == 'score' else None))
        ]
        for issue in issues:
            print(issue, file=sys.stderr)
        return 1 if issues else 0
    return 2


if __name__ == "__main__":
    raise SystemExit(_main())
