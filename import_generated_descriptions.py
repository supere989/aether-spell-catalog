"""Add generated interpretations without replacing original spell data."""
import hashlib
import json
import sqlite3
from pathlib import Path

ROOT = Path(__file__).resolve().parent
source = ROOT / 'runes-described.jsonl'
rows = [json.loads(line) for line in source.read_text().splitlines()]
assert len(rows) == len({r['spell_id'] for r in rows})
source_hash = hashlib.sha256(source.read_bytes()).hexdigest()
connection = sqlite3.connect(ROOT / 'catalog.sqlite')
connection.execute('PRAGMA foreign_keys=ON')
backup = ROOT / 'backups' / 'catalog-before-generated-descriptions.sqlite'
backup.parent.mkdir(exist_ok=True)
if not backup.exists():
    with sqlite3.connect(backup) as destination:
        connection.backup(destination)

def baseline_hash():
    digest = hashlib.sha256()
    for row in connection.execute('SELECT id,name,description FROM spell_index ORDER BY id'):
        digest.update(json.dumps(row, ensure_ascii=False).encode())
    return digest.hexdigest()

before = baseline_hash()
with connection:
    connection.execute('''CREATE TABLE IF NOT EXISTS generated_spell_descriptions (
        spell_id INTEGER PRIMARY KEY REFERENCES spell_index(id),
        generated_description TEXT NOT NULL,
        status TEXT NOT NULL,
        basis TEXT NOT NULL,
        scope_candidates_json TEXT NOT NULL,
        evidence_json TEXT NOT NULL,
        source_sha256 TEXT NOT NULL,
        runtime_verified INTEGER NOT NULL DEFAULT 0 CHECK(runtime_verified=0),
        planner_eligible INTEGER NOT NULL DEFAULT 0 CHECK(planner_eligible=0)
    )''')
    for r in rows:
        assert r['planner_eligible'] is False
        connection.execute('''INSERT INTO generated_spell_descriptions
            VALUES(?,?,?,?,?,?,?,0,0)
            ON CONFLICT(spell_id) DO UPDATE SET
              generated_description=excluded.generated_description,
              status=excluded.status,basis=excluded.basis,
              scope_candidates_json=excluded.scope_candidates_json,
              evidence_json=excluded.evidence_json,source_sha256=excluded.source_sha256''',
            (r['spell_id'], r['generated_description'], r['status'], r['description_basis'],
             json.dumps(r['scope_candidates']), json.dumps(r,ensure_ascii=False), source_hash))
    assert baseline_hash() == before
    assert not connection.execute('PRAGMA foreign_key_check').fetchall()
assert connection.execute('PRAGMA integrity_check').fetchone()[0] == 'ok'
for r in rows:
    stored = connection.execute('SELECT evidence_json FROM generated_spell_descriptions WHERE spell_id=?', (r['spell_id'],)).fetchone()
    assert json.loads(stored[0]) == r
report = {'imported':len(rows),'original_spell_descriptions_unchanged':True,
          'original_spell_text_sha256':before,'json_evidence_matches':True,
          'foreign_keys':'ok','integrity':'ok','source_sha256':source_hash,
          'backup':str(backup)}
(ROOT/'description-import-verification.json').write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps(report,indent=2))
