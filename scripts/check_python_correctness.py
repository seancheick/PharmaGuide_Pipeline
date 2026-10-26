#!/usr/bin/env python3
"""Reject new correctness diagnostics; never rewrite source or the baseline.

Baseline entries identify exact path/rule/message/source fragments, with repeated
entries counting separate occurrences. Line movement is allowed; a new occurrence
is not. Baseline changes require an explicitly reviewed diff, not an update flag.
"""
from collections import Counter
import json
from pathlib import Path
import subprocess
import sys
import tomllib

ROOT = Path(__file__).resolve().parents[1]
BASELINE = ROOT / 'scripts/contracts/python_correctness_baseline.json'


def collect(root):
    root = Path(root).resolve()
    paths = subprocess.check_output(
        ['git', 'ls-files', '-z', '--', '*.py'], cwd=root,
    ).decode().split('\0')
    paths = [path for path in paths if path]
    if not paths:
        raise ValueError('No tracked Python files found')
    result = subprocess.run(
        [sys.executable, '-m', 'ruff', 'check', '--config', str(root / 'ruff.toml'),
         '--no-cache', '--ignore-noqa', '--output-format', 'json', '--', *paths],
        cwd=root, capture_output=True, text=True,
    )
    if result.returncode not in (0, 1):
        raise ValueError(f'Ruff could not complete: {result.stderr.strip()}')
    findings = []
    for item in json.loads(result.stdout):
        path = Path(item['filename'])
        lines = path.read_text().splitlines()
        start, end = item['location']['row'], item['end_location']['row']
        findings.append({
            'path': path.relative_to(root).as_posix(),
            'code': item['code'] or 'invalid-syntax',
            'message': item['message'],
            'source': '\n'.join(line.strip() for line in lines[start - 1:end]),
        })
    return findings


def read_baseline(path, root=ROOT):
    baseline = json.loads(Path(path).read_text())
    config = tomllib.loads((Path(root) / 'ruff.toml').read_text())
    if config['required-version'] != '==' + baseline['ruff_version']:
        raise ValueError('Baseline Ruff version differs from pinned configuration')
    entries = baseline['findings']
    for entry in entries:
        if (set(entry) != {'path', 'code', 'message', 'source'}
                or any(not isinstance(value, str) or not value for value in entry.values())
                or Path(entry['path']).is_absolute() or '..' in Path(entry['path']).parts
                or entry['code'] not in config['lint']['select']):
            raise ValueError('Invalid baseline entry; syntax failures cannot be baselined')
    return entries


def new_findings(current, baseline):
    remaining = Counter(json.dumps(item, sort_keys=True) for item in baseline)
    new = []
    for item in current:
        key = json.dumps(item, sort_keys=True)
        if remaining[key]:
            remaining[key] -= 1
        else:
            new.append(item)
    return new


def main():
    try:
        current = collect(ROOT)
        new = new_findings(current, read_baseline(BASELINE, ROOT))
    except (OSError, ValueError, KeyError, TypeError, subprocess.SubprocessError) as exc:
        print(f'Python correctness check failed: {exc}', file=sys.stderr)
        return 2
    for item in new:
        print(f"{item['path']}: {item['code']} {item['message']}\n  {item['source']}")
    print(f'Python correctness: {len(new)} new; {len(current) - len(new)} existing findings.')
    return 1 if new else 0


if __name__ == '__main__':
    raise SystemExit(main())
