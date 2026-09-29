import re, json, subprocess, os, sys
from pathlib import Path
from collections import defaultdict
root = Path('.').resolve()
tracked = subprocess.run(['git','ls-files'], capture_output=True, text=True).stdout.splitlines()
tracked_set = set(tracked)
docs = [f for f in tracked if (f.endswith('.md') or f.endswith('.txt')) and not f.startswith(('scripts/products/','reports/')) and not f.endswith('.ocr.txt') and 'requirements' not in f]
code_files = [f for f in tracked if f.endswith(('.py','.sh','.js','.sql','.json','.toml','.yaml','.yml'))]
# symbol table from python
symbols = set()
for f in tracked:
    if f.endswith('.py'):
        try: txt = Path(f).read_text(errors='ignore')
        except: continue
        symbols.update(re.findall(r'^\s*(?:def|class)\s+([A-Za-z_]\w*)', txt, re.M))
basenames = defaultdict(list)
for f in tracked: basenames[os.path.basename(f)].append(f)
live_pointer_files = [f for f in tracked if f in ('AGENTS.md','CLAUDE.md','README.md','scripts/GLOSSARY.md') or f.startswith(('.claude/rules/','.claude/skills/')) or f.endswith(('.py','.sh'))]
live_text = {f: Path(f).read_text(errors='ignore') for f in live_pointer_files if Path(f).is_file()}
doc_text = {f: Path(f).read_text(errors='ignore') for f in docs if Path(f).is_file()}
MARK = re.compile(r'\b(superseded|archived|archive|deprecated|obsolete|historical|history|do not use|no longer|stale|legacy|out of date|outdated|retired|replaced by)\b', re.I)
rows = []
for f in docs:
    txt = doc_text.get(f, '')
    head = '\n'.join(txt.splitlines()[:40])
    last = subprocess.run(['git','log','-1','--format=%cs','--',f], capture_output=True, text=True).stdout.strip()
    first = subprocess.run(['git','log','--diff-filter=A','--format=%cs','--',f], capture_output=True, text=True).stdout.strip().splitlines()
    first = first[-1] if first else last
    # outbound file refs
    refs = set(re.findall(r'(?<![\w/])((?:[\w.-]+/)*[\w.-]+\.(?:py|sh|json|md|sql|js))(?![\w/])', txt))
    refs = {r for r in refs if not r.startswith(('http','www')) and len(r) > 4}
    alive = dead = 0; dead_list = []
    for r in refs:
        b = os.path.basename(r)
        if r in tracked_set or b in basenames or Path(r).exists(): alive += 1
        else: dead += 1; dead_list.append(r)
    # symbol refs `name()`
    syms = set(re.findall(r'`([A-Za-z_]\w*)\(\)`', txt)) | set(re.findall(r'::([A-Za-z_]\w*)', txt))
    sym_dead = [s for s in syms if s not in symbols]
    # inbound
    bn = os.path.basename(f); stem = bn.rsplit('.',1)[0]
    live_in = [g for g, t in live_text.items() if g != f and (bn in t or (len(stem) > 12 and stem in t))]
    doc_in = [g for g, t in doc_text.items() if g != f and bn in t]
    markers = sorted(set(m.lower() for m in MARK.findall(head)))
    rows.append({'path': f, 'dir': '/'.join(f.split('/')[:2]) if '/' in f else '.', 'bytes': len(txt), 'first': first, 'last': last,
                 'refs': len(refs), 'dead_refs': dead, 'dead_list': sorted(dead_list)[:6], 'syms': len(syms), 'dead_syms': len(sym_dead), 'dead_sym_list': sorted(sym_dead)[:6],
                 'live_inbound': live_in, 'doc_inbound': len(doc_in), 'markers': markers})
json.dump(rows, open(sys.argv[1], 'w'), indent=1)
print(len(rows), 'docs censused;', len(symbols), 'python symbols')
