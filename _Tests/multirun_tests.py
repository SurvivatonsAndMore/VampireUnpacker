from typing import Iterable
from unittest import TestCase, main as ut_main

from Source.Utility.multirun import starmap_multiprocess, map_multiprocess


def many_args(a: int, b: int, c: int) -> int:
    return 3 * a + 7 * b + 13 * c


def single_arg(a: int) -> int:
    return 101 * a


class _TestRunsTests(TestCase):
    """
    Correct sync implementation of other multirun functions
    """

    @staticmethod
    def _run_test(func, args):
        return [isinstance(arg, Iterable) and func(*arg) or func(arg) for arg in args]

    def test_many_args(self):
        args = [(n, n - 1, n - 2) for n in range(10)]
        ret = self._run_test(many_args, args)
        expected = [many_args(*a) for a in args]
        self.assertEqual(ret, expected)

    def test_single_args(self):
        args = [*range(10)]
        ret = self._run_test(single_arg, args)
        expected = [single_arg(a) for a in args]
        self.assertEqual(ret, expected)


class MultiprocessTests(TestCase):
    def test_mp_starmap(self):
        args = [(n, n - 1, n - 2) for n in range(10)]
        ret = starmap_multiprocess(many_args, args)
        expected = [many_args(*a) for a in args]
        self.assertEqual(ret, expected)

    def test_mp_map(self):
        args = [n for n in range(10)]
        ret = map_multiprocess(single_arg, args)
        expected = [single_arg(a) for a in args]
        self.assertEqual(ret, expected)


if __name__ == "__main__":
    ut_main()
