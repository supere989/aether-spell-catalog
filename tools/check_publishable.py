"""Refuse to push what must not be public (the repo is public): files > 2 MB, game-derived data, credentials, internal addresses."""
import fnmatch, re, subprocess, sys
LIMIT = 2_000_000
DATA = ('*.sqlite', '*.jsonl', '*.png', 'webui/assets', 'webui/assets/*', 'webui/tools/mpqextract', 'webui/tools/mpqtool', 'backups/*',
        'GEAR-SETS.md', 'RUNE-DESCRIPTIONS.md', 'SET-CLASS-MAPPING.md')
SECRET = re.compile(r'''(?i)(passw(or)?d|secret|token|api[_-]?key)\s*[=:]\s*['"][^'"\s]{6,}|BEGIN [A-Z ]*PRIVATE KEY|gh[pousr]_[A-Za-z0-9]{20}''')
INTERNAL = re.compile(r'\b(10\.150\.\d+\.\d+|10\.99\.\d+\.\d+|100\.(6[4-9]|[7-9]\d|1[01]\d|12[0-7])\.\d+\.\d+)\b')

def problems(files):
    out = []
    for path, size, text in files:
        if size > LIMIT: out.append(f'{path}: {size} bytes > {LIMIT}')
        if any(fnmatch.fnmatch(path, p) for p in DATA) or (path.endswith('.json') and not fnmatch.fnmatch(path, 'planner/example-*.json')):
            out.append(f'{path}: generated/game data must stay local')
        if SECRET.search(text): out.append(f'{path}: looks like a credential')
        if INTERNAL.search(text): out.append(f'{path}: names an internal address')
    return out

def tracked():
    top = subprocess.run(['git', 'rev-parse', '--show-toplevel'], capture_output=True, check=True, text=True).stdout.strip()  # whole repo from any cwd
    names = subprocess.run(['git', 'ls-files', '-z'], capture_output=True, check=True, cwd=top).stdout.decode().split('\0')
    res = []
    for n in filter(None, names):
        try: data = open(f'{top}/{n}', 'rb').read()
        except OSError: continue
        res.append((n, len(data), data.decode('utf-8', 'replace') if b'\0' not in data[:8192] and 'vendor/' not in n else ''))
    return res

if __name__ == '__main__':
    p = problems(tracked())
    for line in p: print('refusing to push:', line, file=sys.stderr)
    sys.exit(1 if p else 0)
