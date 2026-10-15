"""What the simulator has done since it started (SAI): route counters, outcomes, the engine's choice distribution. Thread-safe, in memory."""
import json, threading, time
from collections import Counter, defaultdict
DEFENSE = {'miss', 'dodge', 'parry', 'block', 'absorb', 'hit'}

class Counters:
    def __init__(self):
        self.lock = threading.Lock(); self.c = Counter(); self.casts = defaultdict(Counter); self.outcomes = Counter(); self.runs = 0
        self.started = time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())
    def bump(self, name, n=1):
        with self.lock: self.c[name] += n
    def record_run(self, config, result):
        cls = [str(s.get('class_id')) for s in config.get('slots', [])]
        with self.lock:
            self.runs += 1
            for e in result.get('events', []):
                if e.get('kind') == 'cast' and isinstance(e.get('actor'), int) and e['actor'] < len(cls):
                    self.casts[cls[e['actor']]][e.get('ability') or '?'] += 1
                elif e.get('kind') in DEFENSE and e.get('target') != 'enemy': self.outcomes[e['kind']] += 1  # rolls against the group, not its own misses
    def snapshot(self):
        with self.lock:
            return {'counters': dict(self.c), 'started': self.started,
                    'engine': {'runs': self.runs, 'casts': {k: dict(v) for k, v in self.casts.items()}, 'outcomes': dict(self.outcomes)}}

def read_json(path, default):
    try: return json.loads(path.read_text())
    except (OSError, ValueError): return default

def last_line(path):
    try:
        lines = path.read_text().strip().splitlines()
        return json.loads(lines[-1]) if lines else None
    except (OSError, ValueError): return None
