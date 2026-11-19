import copy
import unittest
from dedupe import dedupe


class T(unittest.TestCase):
    def test_basic(self):
        recs = [
            {'email': ' A@x.com', 'name': 'a1', 'updated_at': '2026-01-01T00:00:00'},
            {'email': 'b@x.com', 'name': 'b', 'updated_at': '2026-01-01T00:00:00'},
            {'email': 'a@X.com ', 'name': 'a2', 'updated_at': '2026-02-01T00:00:00'},
        ]
        out = dedupe(recs)
        self.assertEqual([r['email'] for r in out], ['a@x.com', 'b@x.com'])
        self.assertEqual(out[0]['name'], 'a2')

    def test_tie_keeps_later(self):
        recs = [
            {'email': 'c@x.com', 'name': 'first', 'updated_at': '2026-01-01T00:00:00'},
            {'email': 'C@x.com', 'name': 'second', 'updated_at': '2026-01-01T00:00:00'},
        ]
        self.assertEqual(dedupe(recs)[0]['name'], 'second')

    def test_no_mutation(self):
        recs = [{'email': ' Z@x.com', 'name': 'z', 'updated_at': '2026-01-01T00:00:00'}]
        before = copy.deepcopy(recs)
        dedupe(recs)
        self.assertEqual(recs, before)

    def test_empty(self):
        self.assertEqual(dedupe([]), [])
