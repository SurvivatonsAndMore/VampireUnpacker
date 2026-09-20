from concurrent.futures import Executor, ProcessPoolExecutor, ThreadPoolExecutor
from typing import Callable, Iterable, ParamSpec, TypeVar

from Source.Utility.constants import IS_DEBUG

P = ParamSpec("P")
T = TypeVar("T")


def starmap_multiprocess[**P, T](
        func: Callable[P, T],
        args: Iterable[P.args],
        *,
        chunksize: int = 1,
        is_multiprocess: bool = True,
        executor_cls: type[Executor] = ProcessPoolExecutor,
) -> list[T]:
    """
    Applies starmap for CPU bound tasks
    """
    if not args:
        return []

    if IS_DEBUG:
        executor_cls = ThreadPoolExecutor

    with executor_cls() as ex:
        return list(ex.map(func, *zip(*args), chunksize=chunksize))


def map_multiprocess[**P, T](
        func: Callable[P, T],
        args: Iterable[P.args],
        *,
        chunksize: int = 1,
        is_multiprocess: bool = True,
        executor_cls: type[Executor] = ProcessPoolExecutor,
) -> list[T]:
    """
    Applies map for CPU bound tasks
    """
    if not args:
        return []

    if IS_DEBUG:
        executor_cls = ThreadPoolExecutor

    with executor_cls() as ex:
        return list(ex.map(func, args, chunksize=chunksize))


def starmap_multithread[**P, T](
        func: Callable[P, T],
        args: Iterable[P.args],
        *,
        max_workers: int = None,
) -> list[T]:
    """
    Applies starmap for I/O bound tasks
    """
    if not args:
        return []

    with ThreadPoolExecutor(max_workers=max_workers) as ex:
        return list(ex.map(func, *zip(*args)))


def map_multithread[**P, T](
        func: Callable[P, T],
        args: Iterable[P.args],
        *,
        max_workers: int = None,
) -> list[T]:
    """
    Applies map for I/O bound tasks
    """
    if not args:
        return []

    with ThreadPoolExecutor(max_workers=max_workers) as ex:
        return list(ex.map(func, args))
