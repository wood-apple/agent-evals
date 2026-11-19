import random
import unittest
from search import find_first


def ref(items, t):
    return items.index(t) if t in items else -1


class T(unittest.TestCase):
    def test_simple(self):
        self.assertEqual(find_first([1, 2, 3], 2), 1)
        self.assertEqual(find_first([], 1), -1)
        self.assertEqual(find_first([5], 5), 0)

    def test_duplicates(self):
        self.assertEqual(find_first([1, 2, 2, 2, 3], 2), 1)
        self.assertEqual(find_first([2, 2, 2], 2), 0)

    def test_random(self):
        rng = random.Random(0)
        for _ in range(500):
            items = sorted(rng.randint(0, 20) for _ in range(rng.randint(0, 30)))
            t = rng.randint(-1, 21)
            self.assertEqual(find_first(items, t), ref(items, t), (items, t))
