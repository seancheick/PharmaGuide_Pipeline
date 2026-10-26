#!/usr/bin/env python3
"""Classify committed SHA pairs for the shared required-CI workflow.

Only regular non-executable Markdown in explicit documentation locations can
use the light path. Unknown input defaults to full checks; local dirt is ignored.
"""
import argparse
from pathlib import Path
import re
import subprocess
import sys


def _git(repo, *args):
    return subprocess.check_output(['git', '-C', str(repo), *args], stderr=subprocess.PIPE)


def _documentation(path):
    return path.endswith('.md') and (
        path in {'README.md', 'AGENTS.md', 'CLAUDE.md', '.claude/state/CURRENT_HANDOFF.md'}
        or path.startswith(('docs/', 'knowledge/', '.claude/skills/', 'scripts/audits/'))
    )


def classify(repo, base, head):
    try:
        for sha in (base, head):
            if not re.fullmatch(r'[0-9a-f]{40}|[0-9a-f]{64}', sha) or not int(sha, 16):
                return 'full'
            if _git(repo, 'rev-parse', '--verify', sha + '^{commit}').decode().strip() != sha:
                return 'full'
        fields = _git(repo, 'diff', '--raw', '-z', '--no-abbrev', '--no-renames',
                      base, head, '--').decode('utf-8').split('\0')
        if fields == [''] or fields[-1] != '' or len(fields) % 2 != 1:
            return 'full'
        for index in range(0, len(fields) - 1, 2):
            metadata, path = fields[index:index + 2]
            old_mode, new_mode, _, _, status = metadata.removeprefix(':').split()
            if (not metadata.startswith(':') or status not in {'A', 'M', 'D'}
                    or any(mode not in {'000000', '100644'} for mode in (old_mode, new_mode))
                    or not _documentation(path)):
                return 'full'
        return 'docs'
    except (OSError, ValueError, subprocess.SubprocessError):
        return 'full'


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--repo', type=Path, required=True)
    parser.add_argument('--base', default='')
    parser.add_argument('--head', default='')
    args = parser.parse_args()
    scope = classify(args.repo, args.base, args.head)
    print(scope)
    if scope == 'docs':
        result = subprocess.run(['git', '-C', str(args.repo), 'diff', '--check',
                                 args.base, args.head, '--'], capture_output=True, text=True)
        if result.returncode:
            print('Documentation whitespace check failed:\n' + result.stdout + result.stderr,
                  file=sys.stderr)
            return 1
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
