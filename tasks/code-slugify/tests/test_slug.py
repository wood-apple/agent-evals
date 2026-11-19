import unittest
from slug import slugify


class T(unittest.TestCase):
    def test_basic(self):
        self.assertEqual(slugify('Hello, World!'), 'hello-world')
        self.assertEqual(slugify('  --Already--slugged--  '), 'already-slugged')

    def test_translit(self):
        self.assertEqual(slugify('Crème Brûlée'), 'creme-brulee')
        self.assertEqual(slugify('Straße in Ørsted'), 'strasse-in-orsted')

    def test_truncate(self):
        self.assertEqual(slugify('the quick brown fox jumps over the lazy dog', 20), 'the-quick-brown-fox')
        self.assertEqual(slugify('abcdefghijklmnopqrstuvwxyz', 10), 'abcdefghij')

    def test_empty(self):
        self.assertEqual(slugify('!!!'), '')
        self.assertEqual(slugify(''), '')
