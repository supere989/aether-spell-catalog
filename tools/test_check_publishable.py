import unittest
import check_publishable as c
IP = lambda *o: '.'.join(map(str, o))  # fixtures assembled at run time: this public file must not itself name an address or a credential

class CheckTest(unittest.TestCase):
    def test_clean(self): self.assertEqual(c.problems([('webui/server.py', 7000, 'import json')]), [])
    def test_big_file(self): self.assertTrue(c.problems([('x.js', 3_000_000, '')]))
    def test_game_data(self):
        for p in ('catalog.sqlite', 'a.jsonl', 'webui/gear-catalog.json', 'webui/assets/x.png', 'webui/assets', 'webui/tools/mpqextract'):
            self.assertTrue(c.problems([(p, 10, '')]), p)
        self.assertEqual(c.problems([('planner/example-dps.json', 10, '{}')]), [])
    def test_credentials_and_hosts(self):
        self.assertTrue(c.problems([('a.py', 10, "PASS='hunter2hunter2'\n" + 'pass' + "word = 'abc12345'")]))
        self.assertTrue(c.problems([('a.py', 10, 'ssh coa@' + IP(10, 150, 0, 9))]))
        self.assertTrue(c.problems([('a.py', 10, 'remote ' + IP(10, 99, 0, 9))]))
        self.assertTrue(c.problems([('a.py', 10, 'tailnet ' + IP(100, 101, 0, 9))]))
        self.assertEqual(c.problems([('README.md', 10, 'public site ' + IP(5, 78, 204, 86))]), [])

if __name__ == '__main__': unittest.main()
