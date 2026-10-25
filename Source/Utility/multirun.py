from concurrent.futures import Executor, ProcessPoolExecutor, ThreadPoolExecutor
from typing import Callable, Iterable, ParamSpec, TypeVar

from Source.Utility.constants import IS_DEBUG, PROGRESS_BAR_FUNC_TYPE

P = ParamSpec("P")
T = TypeVar("T")

def _collect_with_progress[T](
        iterator: Iterable[T],
        total: int | None,
        progress: PROGRESS_BAR_FUNC_TYPE | None,
) -> list[T]:
    if progress is None:
        return list(iterator)

    i = 0
    if total is not None:
        progress(i, total)
    else:
        progress(i, i + 1)

    results: list[T] = []
    for i, result in enumerate(iterator, 1):
        results.append(result)
        if total is not None:
            progress(i, total)
        else:
            progress(i, i+1)

    progress(i, i)

    return results

def len_or_none(iterable) -> int | None:
    return len(iterable) if hasattr(iterable, '__len__') else None

def starmap_multiprocess[**P, T](
        func: Callable[P, T],
        args: Iterable[P.args],
        *,
        chunksize: int = 1,
        is_multiprocess: bool = True,
        executor_cls: type[Executor] = ProcessPoolExecutor,
        progress: PROGRESS_BAR_FUNC_TYPE | None = None,
) -> list[T]:
    """
    Applies starmap for CPU bound tasks
    """
    if not args:
        return []

    if IS_DEBUG:
        executor_cls = ThreadPoolExecutor

    with executor_cls() as ex:
        return _collect_with_progress(
            ex.map(func, *zip(*args), chunksize=chunksize),
            len_or_none(args),
            progress,
        )


def map_multiprocess[**P, T](
        func: Callable[P, T],
        args: Iterable[P.args],
        *,
        chunksize: int = 1,
        is_multiprocess: bool = True,
        executor_cls: type[Executor] = ProcessPoolExecutor,
        progress: PROGRESS_BAR_FUNC_TYPE | None = None,
) -> list[T]:
    """
    Applies map for CPU bound tasks
    """
    if not args:
        return []

    if IS_DEBUG:
        executor_cls = ThreadPoolExecutor

    with executor_cls() as ex:
        return _collect_with_progress(
            ex.map(func, args, chunksize=chunksize),
            len_or_none(args),
            progress,
        )


def starmap_multithread[**P, T](
        func: Callable[P, T],
        args: Iterable[P.args],
        *,
        max_workers: int = None,
        progress: PROGRESS_BAR_FUNC_TYPE | None = None,
) -> list[T]:
    """
    Applies starmap for I/O bound tasks
    """
    if not args:
        return []

    with ThreadPoolExecutor(max_workers=max_workers) as ex:
        return _collect_with_progress(
            ex.map(func, *zip(*args)),
            len_or_none(args),
            progress,
        )


def map_multithread[**P, T](
        func: Callable[P, T],
        args: Iterable[P.args],
        *,
        max_workers: int = None,
        progress: PROGRESS_BAR_FUNC_TYPE | None = None,
) -> list[T]:
    """
    Applies map for I/O bound tasks
    """
    if not args:
        return []

    with ThreadPoolExecutor(max_workers=max_workers) as ex:
        return _collect_with_progress(
            ex.map(func, args),
            len_or_none(args),
            progress,
        )
