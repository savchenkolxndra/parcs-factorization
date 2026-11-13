# -*- coding: utf-8 -*-
"""
Локальний запуск PARCS-рішення без хмари (Python 3).

Емулює те, що робить PARCS: створює Solver зі списком "воркерів", у яких виклик
mymap(...) асинхронний і повертає об'єкт із полем .value (як Pyro4-проксі).
Кожен воркер - окремий процес, тому на багатоядерному ПК обчислення справді паралельні.
Потрібен пакет Pyro4 (pip install Pyro4) - лише заради декоратора @expose.

Запуск:  python tools/local_run.py solution/factorization_parallel.py input/semiprime_40bit.txt 4 out.txt
"""
import concurrent.futures
import importlib.util
import sys

_solution_path = None


def _load(path):
    spec = importlib.util.spec_from_file_location("solution", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _call(path, method, args):
    # виконується в окремому процесі - як на воркері PARCS
    return getattr(_load(path).Solver, method)(*args)


class _Future:
    def __init__(self, future):
        self._future = future

    @property
    def value(self):
        return self._future.result()


class _Worker:
    def __init__(self, pool, path):
        self._pool, self._path = pool, path

    def __getattr__(self, method):
        def remote(*args):
            return _Future(self._pool.submit(_call, self._path, method, args))
        return remote


def main():
    if len(sys.argv) != 5:
        print(__doc__)
        sys.exit(1)
    path, input_file, n_workers, output_file = sys.argv[1], sys.argv[2], int(sys.argv[3]), sys.argv[4]
    module = _load(path)
    pools = [concurrent.futures.ProcessPoolExecutor(max_workers=1) for _ in range(n_workers)]
    try:
        workers = [_Worker(pool, path) for pool in pools]
        module.Solver(workers, input_file, output_file).solve()
    finally:
        for pool in pools:
            pool.shutdown()
    with open(output_file, encoding="utf-8") as f:
        print(f.read(), end="")


if __name__ == "__main__":
    main()
