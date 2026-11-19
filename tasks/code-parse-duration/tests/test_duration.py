import unittest
from duration import parse_duration


class T(unittest.TestCase):
    def test_basic(self):
        self.assertEqual(parse_duration('45s'), 45)
        self.assertEqual(parse_duration('1h30m'), 5400)
        self.assertEqual(parse_duration('2d'), 172800)
        self.assertEqual(parse_duration('1d2h3m4s'), 93784)

    def test_spaces(self):
        self.assertEqual(parse_duration('1h 5m'), 3900)

    def test_zero_parts(self):
        self.assertEqual(parse_duration('0h10m'), 600)

    def test_errors(self):
        for bad in ['', '10', 'h', '5x', '1m1h', '1h1h', 'abc', '1.5h']:
            with self.assertRaises(ValueError, msg=bad):
                parse_duration(bad)
