import unittest
from roman import from_roman, to_roman


class T(unittest.TestCase):
    def test_to(self):
        for n, s in [(1, 'I'), (4, 'IV'), (9, 'IX'), (14, 'XIV'), (40, 'XL'), (90, 'XC'), (400, 'CD'), (1994, 'MCMXCIV'), (3999, 'MMMCMXCIX')]:
            self.assertEqual(to_roman(n), s)

    def test_roundtrip(self):
        for n in range(1, 4000):
            self.assertEqual(from_roman(to_roman(n)), n)

    def test_invalid(self):
        for bad in [0, 4000, -1]:
            with self.assertRaises(ValueError):
                to_roman(bad)
        for bad in ['', 'IIII', 'IC', 'VX', 'MMMM', 'abc', 'iv']:
            with self.assertRaises(ValueError, msg=bad):
                from_roman(bad)
