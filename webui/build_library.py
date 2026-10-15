"""Build the complete static asset library the public simulator serves from the VPS (spec §4). Resumable, atomic per file, process pool.
Every file that cannot be produced is ledgered (missing-assets.jsonl), never skipped silently."""
import argparse, json, os, shutil, time
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path
import paths
BASE = Path(__file__).resolve().parent
OUT = {'texture': ('assets', '.png'), 'item': ('item-models', '.json')}

def target(kind, ident):
    folder, ext = OUT[kind]; return paths.path('library') / folder / (ident + ext)

def make_texture(ident):
    import asset_io
    t = target('texture', ident); t.parent.mkdir(parents=True, exist_ok=True); tmp = t.with_suffix('.tmp.png')
    asset_io.decode_texture(asset_io.extract(ident)).save(tmp); tmp.replace(t); return True

def make_item(ident, skin):
    import export_item_mesh
    t = target('item', ident); t.parent.mkdir(parents=True, exist_ok=True); tmp = t.with_suffix('.tmp')
    tmp.write_text(json.dumps(export_item_mesh.export(ident, skin), separators=(',', ':'))); tmp.replace(t); return True

def _one(job, texture, item):
    kind, ident, skin = job
    try: (texture(ident) if kind == 'texture' else item(ident, skin)); return kind, ident, None
    except Exception as e:  # noqa: BLE001 — every failure is ledgered with its reason
        return kind, ident, f'{type(e).__name__}: {e}'[:300]

def run_jobs(jobs, workers, texture=make_texture, item=make_item):
    led = paths.path('ledger'); led.mkdir(parents=True, exist_ok=True); counts = {'textures': 0, 'item_models': 0, 'missing': 0}
    for folder, _ in OUT.values(): (paths.path('library') / folder).mkdir(parents=True, exist_ok=True)
    todo = [j for j in jobs if not target(j[0], j[1]).is_file()]
    with (led / 'missing-assets.jsonl').open('a') as miss:
        def note(kind, ident, err):
            if err:
                counts['missing'] += 1
                rec = _record(ident)
                miss.write(json.dumps({'ts': time.strftime('%FT%TZ', time.gmtime()), 'kind': kind, 'id': ident, 'error': err, **rec}) + '\n')
            else: counts['textures' if kind == 'texture' else 'item_models'] += 1
        if workers <= 1:
            for j in todo: note(*_one(j, texture, item))
        else:
            with ProcessPoolExecutor(workers) as pool:
                for f in as_completed([pool.submit(_one, j, texture, item) for j in todo]): note(*f.result())
    return counts

def _record(ident):
    try:
        import asset_io; r = asset_io.manifest()['files'].get(ident) or {}
        return {'archive': r.get('archive'), 'path': r.get('path')}
    except (OSError, ValueError): return {}

def write_visuals(src):
    from server import prefixed
    t = paths.path('library') / 'visuals.json'; t.parent.mkdir(parents=True, exist_ok=True); tmp = t.with_suffix('.tmp')
    tmp.write_bytes(prefixed(Path(src).read_bytes(), '/simulator')); tmp.replace(t)

def write_generation(counts):
    g = paths.path('library') / 'generation.json'; g.parent.mkdir(parents=True, exist_ok=True)
    prev = json.loads(g.read_text()).get('generation', 0) if g.is_file() else 0
    tmp = g.with_suffix('.tmp'); tmp.write_text(json.dumps({'generation': prev + 1, 'built': time.strftime('%FT%TZ', time.gmtime()), **counts})); tmp.replace(g)

def jobs_from_visuals():
    import asset_io, server
    files = asset_io.manifest()['files']
    tex = [('texture', k, None) for k, r in files.items() if r['path'].lower().endswith('.blp')]
    return tex + [('item', k, s) for k, s in sorted(server.item_models().items())]

if __name__ == '__main__':
    a = argparse.ArgumentParser(); a.add_argument('--workers', type=int, default=os.cpu_count()); a.add_argument('--limit', type=int)
    args = a.parse_args(); jobs = jobs_from_visuals()[:args.limit] if args.limit else jobs_from_visuals()
    counts = run_jobs(jobs, args.workers)
    models = paths.path('library') / 'models'; models.mkdir(parents=True, exist_ok=True)
    for f in (BASE / 'assets/models').glob('*.json'): shutil.copy2(f, models / f.name)
    write_visuals(BASE / 'assets/visuals.json')
    counts['models'] = len(list(models.glob('*.json')))
    counts['textures'] = len(list((paths.path('library') / 'assets').glob('*.png')))
    counts['item_models'] = len(list((paths.path('library') / 'item-models').glob('*.json')))
    write_generation(counts)
    miss = paths.path('ledger') / 'missing-assets.jsonl'   # published with the library: what it lacks and why
    if miss.is_file():
        tmp = paths.path('library') / 'missing-assets.jsonl.tmp'; shutil.copy2(miss, tmp); tmp.replace(tmp.with_suffix(''))
    print(json.dumps(counts))
