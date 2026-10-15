"""sim-reload: live edits on the public VM go live only after tests + a candidate smoke pass (spec §3). A failed attempt leaves the live
server on the old code; every attempt is a reload.jsonl row (SAI). Polls once a second, 2 s debounce — no inotify dependency."""
import argparse, json, subprocess, sys, time, urllib.request
from pathlib import Path
import paths
WATCH = ('*.py', 'webui/*.py', 'planner/*.py', 'webui/static/*', 'webui/static/vendor/*', 'config/*.toml')
DATA = ('catalog.sqlite', 'webui/gear-catalog.json', 'webui/mechanics-source.json', 'webui/set-class-mapping.json', 'webui/assets/visuals.json')
# The shape webui/static/app.js POSTs (balanced 5-slot group); short, so the smoke stays a few seconds.
SMOKE_SCENARIO = {'size': 5, 'duration': 20, 'mode': 'pve', 'enemy_health': 50000, 'incoming_dps': 350,
                  'slots': [{'class_id': c, 'role': r, 'level': 60, 'power': 1, 'cost_multiplier': 1, 'regen': 10}
                            for c, r in zip((12, 13, 14, 15, 16), ('tank', 'healer', 'damage', 'damage', 'damage'))]}

def scan(root):
    out = {}
    for pat in WATCH:
        for f in root.glob(pat):
            if f.is_file(): out[str(f.relative_to(root))] = f.stat().st_mtime
    for d in DATA:
        f = root / d
        if f.exists(): out[d] = f.stat().st_mtime
    return out

def classify(changed): return 'static' if all(c.startswith('webui/static/') for c in changed) else 'code'

def ledger(row):
    led = paths.path('ledger'); led.mkdir(parents=True, exist_ok=True)
    with (led / 'reload.jsonl').open('a') as f: f.write(json.dumps(row) + '\n')
    return row

def attempt(changed, run_tests, start_candidate, smoke, restart, diffstat=lambda: ''):
    row = {'ts': time.strftime('%FT%TZ', time.gmtime()), 'files': changed[:50], 'kind': classify(changed), 'diff': diffstat()}
    if row['kind'] == 'static': return ledger(row | {'result': 'static-live'})
    ok, err = run_tests()
    if not ok: return ledger(row | {'result': 'tests-failed', 'error': err[-2000:]})
    cand = start_candidate()
    try:
        if cand is not None and cand.poll() is not None:   # ours exited (e.g. a stale candidate holds the port): never smoke someone else's
            return ledger(row | {'result': 'candidate-exited', 'error': f'candidate exited with {cand.poll()} before the smoke'})
        ok, err = smoke()
        if not ok: return ledger(row | {'result': 'smoke-failed', 'error': err[-2000:]})
    finally:
        if cand:
            cand.terminate()
            try: cand.wait(10)
            except subprocess.TimeoutExpired: cand.kill(); cand.wait(5)
    try: restart()
    except Exception as e:  # noqa: BLE001 — a failed restart is ledgered, never silent
        return ledger(row | {'result': 'restart-failed', 'error': f'{type(e).__name__}: {e}'[-2000:]})
    return ledger(row | {'result': 'reloaded'})

def safe_attempt(*a, **kw):
    """attempt(), but an unexpected failure is a ledger row instead of a dead watcher (and a lost edit)"""
    try: return attempt(*a, **kw)
    except Exception as e:  # noqa: BLE001
        row = {'ts': time.strftime('%FT%TZ', time.gmtime()), 'files': (a[0] if a else [])[:50], 'result': 'error', 'error': f'{type(e).__name__}: {e}'[-2000:]}
        try: return ledger(row)
        except OSError: print(json.dumps(row), file=sys.stderr, flush=True); return row

def load_seen():
    try: return json.loads((paths.path('ledger') / 'reload-seen.json').read_text())
    except (OSError, ValueError): return None

def save_seen(seen):
    led = paths.path('ledger'); led.mkdir(parents=True, exist_ok=True); tmp = led / 'reload-seen.json.tmp'
    tmp.write_text(json.dumps(seen)); tmp.replace(led / 'reload-seen.json')

def changed_since(old, now):
    return [] if old is None else sorted(k for k in old.keys() | now.keys() if old.get(k) != now.get(k))

def main():
    a = argparse.ArgumentParser(); a.add_argument('--root', default='/srv/simulator/app'); a.add_argument('--unit', default='sim-server.service')
    a.add_argument('--candidate-port', type=int, default=8799); args = a.parse_args(); root = Path(args.root)
    def run_tests():
        for sub, cmd in (('webui', ['-m', 'unittest', 'discover', '-p', 'test_*.py']), ('planner', ['-m', 'unittest', 'test_evaluate'])):
            try: r = subprocess.run([sys.executable, '-B', *cmd], cwd=root / sub, capture_output=True, text=True, timeout=300)
            except subprocess.TimeoutExpired: return False, f'{sub} tests timed out after 300 s'
            if r.returncode: return False, r.stderr
        return True, ''
    def start_candidate():
        p = subprocess.Popen([sys.executable, '-B', str(root / 'webui/server.py'), '--port', str(args.candidate_port), '--bind', '127.0.0.1'],
                             stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        time.sleep(1.5); return p
    def smoke():
        u = f'http://127.0.0.1:{args.candidate_port}'
        try:
            for path in ('/', '/api/classes'): urllib.request.urlopen(u + path, timeout=20).read()
            body = json.dumps(SMOKE_SCENARIO).encode()
            r = urllib.request.urlopen(urllib.request.Request(u + '/api/simulate', body, {'Content-Type': 'application/json'}), timeout=60)
            return ('outcome' in json.load(r)), 'no outcome'
        except Exception as e:  # noqa: BLE001
            return False, f'{type(e).__name__}: {e}'
    def diffstat():
        try: r = subprocess.run(['git', '-C', str(root), 'diff', '--stat', 'HEAD'], capture_output=True, text=True, timeout=30)
        except (OSError, subprocess.SubprocessError): return ''
        return (r.stdout.strip().splitlines() or [''])[-1]
    restart = lambda: subprocess.run(['systemctl', '--user', 'restart', args.unit], check=True, timeout=60)
    seen = scan(root); missed = changed_since(load_seen(), seen)      # edits made while the watcher was down are not lost
    if missed: safe_attempt(missed, run_tests, start_candidate, smoke, restart, diffstat)
    save_seen(seen)
    while True:
        time.sleep(1); now = scan(root)
        if now == seen: continue
        time.sleep(2); now = scan(root)        # debounce: editors save several files
        changed = changed_since(seen, now); seen = now
        safe_attempt(changed, run_tests, start_candidate, smoke, restart, diffstat)
        try: save_seen(seen)
        except OSError as e: print(f'reload-seen not saved: {e}', file=sys.stderr, flush=True)

if __name__ == '__main__': main()
