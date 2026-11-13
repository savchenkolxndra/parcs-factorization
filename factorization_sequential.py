# -*- coding: utf-8 -*-
"""
Послідовна факторизація методом пробних дільників (для порівняння з PARCS-версією).

Класичний алгоритм: вилучаємо 2, далі перебираємо непарні d = 3, 5, 7, ...
поки d <= isqrt(m), де m - поточний залишок; кожен знайдений дільник вилучаємо
повністю. Якщо в кінці m > 1, це просте число.

Запуск локально:  python factorization_sequential.py input/semiprime_62bit.txt output_seq.txt
Або як задача PARCS (клас Solver нижче) - тоді вона рахується на майстрі.
Сумісний із Python 2.7 і Python 3.
"""
from __future__ import print_function, division

import io
import sys
import time

try:
    range = xrange
except NameError:
    pass


def isqrt(n):
    if n < 2:
        return n
    x = 1 << ((n.bit_length() + 1) // 2)
    while True:
        y = (x + n // x) // 2
        if y >= x:
            return x
        x = y


def factorize(n):
    """Повертає (список простих множників, кількість перевірених непарних кандидатів)."""
    factors = []
    m = n
    while m % 2 == 0:
        factors.append(2)
        m //= 2
    checked = 0
    d = 3
    limit = isqrt(m)
    while d <= limit:
        # Перебираємо блок до поточної межі; межа зменшується лише після знахідки,
        # тому всередині блоку не треба щоразу рахувати d*d.
        found = None
        for x in range(d, limit + 1, 2):
            if m % x == 0:
                found = x
                break
        if found is None:
            checked += (limit - d) // 2 + 1
            break
        checked += (found - d) // 2 + 1
        while m % found == 0:
            factors.append(found)
            m //= found
        d = found + 2
        limit = isqrt(m)
    if m > 1:
        factors.append(m)
    return factors, checked


def format_factors(factors):
    parts = []
    for p in sorted(set(factors)):
        e = factors.count(p)
        parts.append("%d^%d" % (p, e) if e > 1 else "%d" % p)
    return " * ".join(parts)


def read_input(path):
    with io.open(path, 'r', encoding='utf-8') as f:
        lines = [line.strip() for line in f]
    lines = [line for line in lines if line and not line.startswith('#')]
    if len(lines) != 1:
        raise ValueError("Expected exactly one number N in the input file")
    n = int(lines[0])
    if n < 2:
        raise ValueError("N must be at least 2")
    return n


def report(n, factors, checked, elapsed):
    product = 1
    for p in factors:
        product *= p
    return (u"N: %d\nWorkers: 0 (sequential)\nCandidates checked: %d\nFactorization: %s\n"
            u"Check: %s\nTotal time: %.3f s\n"
            % (n, checked, format_factors(factors), "OK" if product == n else "FAILED", elapsed))


class Solver:
    """Та сама послідовна програма, оформлена як задача PARCS.
    Її можна надіслати на майстер так само, як паралельну: вона виконується на майстрі
    (воркери не використовуються), тобто на тій самій VM і тому самому Python 2.7."""

    def __init__(self, workers=None, input_file_name=None, output_file_name=None):
        self.input_file_name = input_file_name
        self.output_file_name = output_file_name

    def solve(self):
        t0 = time.time()
        n = read_input(self.input_file_name)
        factors, checked = factorize(n)
        text = report(n, factors, checked, time.time() - t0)
        with io.open(self.output_file_name, 'w', encoding='utf-8') as f:
            f.write(text)
        print("Job Finished")


def main():
    if len(sys.argv) < 2:
        print("Usage: python factorization_sequential.py INPUT [OUTPUT]")
        sys.exit(1)
    t0 = time.time()
    n = read_input(sys.argv[1])
    factors, checked = factorize(n)
    text = report(n, factors, checked, time.time() - t0)
    print(text, end="")
    if len(sys.argv) > 2:
        with io.open(sys.argv[2], 'w', encoding='utf-8') as f:
            f.write(text)


if __name__ == "__main__":
    main()
