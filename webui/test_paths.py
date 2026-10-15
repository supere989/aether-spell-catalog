import os, tempfile, unittest
from pathlib import Path
import paths

class PathsTest(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.TemporaryDirectory(); d = Path(self.dir.name)
        (d / 'pw').write_text('s3cret\n')
        (d / 'p.toml').write_text(f'''[paths]
client_root = "{d}/client"
coa_src = "{d}/src"
asset_catalog = "{d}/ac"
third_party = "{d}/tp"
dbc = "{d}/dbc"
data = "{d}/data"
library = "{d}/lib"
ledger = "{d}/ledger"
[world_db]
host = "127.0.0.1"
port = 3306
user = "simread"
database = "acore_world"
password_file = "{d}/pw"
''')
        os.environ['SIM_PATHS'] = str(d / 'p.toml'); paths.config.cache_clear(); self.d = d
    def tearDown(self):
        os.environ.pop('SIM_PATHS', None); paths.config.cache_clear(); self.dir.cleanup()
    def test_named_paths(self):
        self.assertEqual(paths.path('dbc'), self.d / 'dbc')
    def test_archive_relative_and_absolute(self):
        self.assertEqual(paths.archive('Data/patch.MPQ'), self.d / 'client/Data/patch.MPQ')
        self.assertEqual(paths.archive('/abs/Data/x.MPQ'), Path('/abs/Data/x.MPQ'))
    def test_world_db_reads_password_file(self):
        db = paths.world_db()
        self.assertEqual((db['user'], db['password'], db['port']), ('simread', 's3cret', 3306))
    def test_mysql_args_keep_password_out_of_argv(self):
        argv, env = paths.mysql_args(['--batch'])
        self.assertNotIn('s3cret', ' '.join(argv)); self.assertEqual(env['MYSQL_PWD'], 's3cret')
        self.assertEqual(argv[-1], 'acore_world')
    def test_world_db_kind_defaults_and_reads(self):
        self.assertEqual(paths.world_db_kind(), 'world database (source not labelled)')
        p = self.d / 'p.toml'; p.write_text(p.read_text().replace('[world_db]\n', '[world_db]\nkind = "live realm world database (read-only copy)"\n'))
        paths.config.cache_clear(); self.assertEqual(paths.world_db_kind(), 'live realm world database (read-only copy)')
    def test_unknown_name_is_an_error(self):
        with self.assertRaises(KeyError): paths.path('nope')

class ConfigFileChoiceTest(unittest.TestCase):
    """deferred minor M3: the real config/paths.toml is untracked; the tracked example is the fallback"""
    def test_real_file_then_example(self):
        import tempfile
        from unittest import mock
        with tempfile.TemporaryDirectory() as t:
            repo = Path(t); (repo / 'config').mkdir()
            (repo / 'config/paths.example.toml').write_text('[paths]\ndata = "/example"\n')
            with mock.patch.object(paths, 'REPO', repo), mock.patch.dict(os.environ, {}, clear=False):
                os.environ.pop('SIM_PATHS', None); paths.config.cache_clear()
                self.assertEqual(paths.path('data'), Path('/example'))
                (repo / 'config/paths.toml').write_text('[paths]\ndata = "/real"\n'); paths.config.cache_clear()
                self.assertEqual(paths.path('data'), Path('/real'))
            paths.config.cache_clear()


if __name__ == '__main__': unittest.main()
