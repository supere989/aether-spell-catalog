"""Where the build scripts' inputs and outputs live: config/paths.toml (SIM_PATHS overrides). One file instead of hard-coded paths."""
import os, tomllib
from functools import lru_cache
from pathlib import Path
REPO = Path(__file__).resolve().parent.parent

@lru_cache(maxsize=1)
def config():
    return tomllib.loads(Path(os.environ.get('SIM_PATHS') or REPO / 'config/paths.toml').read_text())

def path(name):
    return Path(config()['paths'][name])

def archive(archive):
    p = Path(archive)
    return p if p.is_absolute() else path('client_root') / p

def world_db():
    w = config()['world_db']
    return dict(host=w['host'], port=int(w['port']), user=w['user'], database=w['database'],
                password=Path(w['password_file']).read_text().strip())

def mysql_args(extra):
    db = world_db(); env = dict(os.environ, MYSQL_PWD=db['password'])
    return ['mysql', '-h', db['host'], '-P', str(db['port']), '-u', db['user'], *extra, db['database']], env
