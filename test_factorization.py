# -*- coding: utf-8 -*-
"""
Перевірка коректності: результати обох версій порівнюються з незалежною
факторизацією (sympy.factorint) для різних N і різної кількості воркерів,
зокрема коли воркерів більше, ніж кандидатів.

Запуск:  pip install Pyro4 sympy  &&  python tests/test_factorization.py
"""
import importlib.util
import os
import random
import tempfile
import contextlib
import io

import sympy

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def load(name):
    spec = importlib.util.spec_from_file_location(name, os.path.join(ROOT, "solution", name + ".py"))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


par = load("factorization_parallel")
seq = load("factorization_sequential")


class Done:
    def __init__(self, value):
        self.value = value


class SyncWorker:
    """Синхронний "воркер": виклик одразу повертає результат у полі .value."""
    def mymap(self, *args):
        return Done(par.Solver.mymap(*args))


def expected(n):
    return sorted(p for p, e in sympy.factorint(n).items() for _ in range(e))


def run_parallel(n, k):
    with tempfile.TemporaryDirectory() as tmp:
        inp, out = os.path.join(tmp, "in.txt"), os.path.join(tmp, "out.txt")
        with open(inp, "w") as f:
            f.write("%d\n" % n)
        with contextlib.redirect_stdout(io.StringIO()):  # PARCS-друк не потрібен у тестах
            par.Solver([SyncWorker() for _ in range(k)], inp, out).solve()
        with open(out, encoding="utf-8") as f:
            text = f.read()
    assert "Check: OK" in text, text
    line = [l for l in text.splitlines() if l.startswith("Factorization: ")][0]
    factors = []
    for part in line[len("Factorization: "):].split(" * "):
        p, _, e = part.partition("^")
        factors += [int(p)] * int(e or 1)
    return sorted(factors)


def check(n):
    exp = expected(n)
    assert sorted(seq.factorize(n)[0]) == exp, ("sequential", n)
    for k in (1, 2, 3, 4, 7, 50):
        got = run_parallel(n, k)
        assert got == exp, ("parallel", n, k, got, exp)


def check_ranges(n, k):
    """Діапазони не перетинаються й разом покривають усі непарні 3..isqrt(m) рівно один раз."""
    m = n
    while m % 2 == 0:
        m //= 2
    limit = par.isqrt(m)
    count = (limit - 1) // 2 if limit >= 3 else 0
    covered = []
    for i in range(k):
        lo = 3 + 2 * (count * i // k)
        hi = 3 + 2 * (count * (i + 1) // k)
        covered += list(range(lo, hi, 2))
    assert covered == list(range(3, limit + 1, 2)), (n, k)


def main():
    random.seed(2026)
    for n in range(2, 3000):
        check(n)
    for x in [0, 1, 2, 3, 15, 16, 17, 10 ** 6, 2 ** 40 - 1]:
        assert par.isqrt(x) == sympy.integer_nthroot(x, 2)[0], x
    special = [
        2 ** 31 - 1,                       # просте Мерсенна
        999983 * 999983,                   # квадрат простого
        3 ** 20, 2 ** 40 * 3 ** 5 * 7,     # великі степені
        2 * 3 * 5 * 7 * 11 * 13 * 17 * 19 * 23 * 29 * 31 * 37,   # багато малих простих
        1000003 * 1000033 * 999979,        # три близькі прості
        9 * 25 * 49 * 1000003,             # квадрати малих простих + велике просте
    ]
    for n in special:
        check(n)
    for _ in range(300):
        n = random.randint(2, 10 ** 12)
        check(n)
        check_ranges(n, random.randint(1, 9))
    for _ in range(40):  # напівпрості з близькими множниками - найгірший випадок
        p = sympy.randprime(10 ** 4, 10 ** 6)
        q = sympy.randprime(10 ** 4, 10 ** 6)
        check(p * q)
    print("All tests passed")


if __name__ == "__main__":
    main()
