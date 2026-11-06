import unittest

from calc import add, sub


class AddTests(unittest.TestCase):
    def test_add(self):
        self.assertEqual(add(2, 3), 5)


class SubTests(unittest.TestCase):
    def test_sub(self):
        self.assertEqual(sub(5, 3), 2)


if __name__ == "__main__":
    unittest.main()
