# -*- coding: utf-8 -*-
"""
PARCS: паралельна факторизація числа методом пробних дільників.

Ідея. Після вилучення множника 2 залишається непарне m. Усі його прості дільники,
крім, можливо, одного, не перевищують L = isqrt(m). Непарні кандидати 3, 5, ..., L
нумеруються від 0 до C-1 і діляться на k рівних неперервних діапазонів за кількістю
воркерів. Кожен воркер перевіряє свій діапазон і повертає знайдені дільники, майстер
об'єднує їх у канонічний розклад (reduce).

Вхідний файл: одне натуральне число N >= 2 (порожні рядки та рядки з # ігноруються).
Код сумісний із Python 2.7 (вузли PARCS, образ hummer12007/parcs-node) і Python 3.
"""
from __future__ import print_function, division

import io
import time

from Pyro4 import expose

try:
    range = xrange  # у Python 2 range створив би величезний список
except NameError:
    pass


def isqrt(n):
    """Цілий квадратний корінь (у Python 2.7 немає math.isqrt). Метод Ньютона."""
    if n < 0:
        raise ValueError("isqrt of a negative number")
    if n < 2:
        return n
    x = 1 << ((n.bit_length() + 1) // 2)  # початкове наближення x >= sqrt(n)
    while True:
        y = (x + n // x) // 2
        if y >= x:
            return x
        x = y


class Solver:

    def __init__(self, workers=None, input_file_name=None, output_file_name=None):
        self.input_file_name = input_file_name
        self.output_file_name = output_file_name
        self.workers = workers
        print("Inited")

    def solve(self):
        print("Job Started")
        n_workers = len(self.workers)
        print("Workers %d" % n_workers)
        t_start = time.time()

        n = self.read_input()

        # 1. Вилучаємо множник 2 на майстрі: це O(log N) операцій.
        twos, m = 0, n
        while m % 2 == 0:
            m //= 2
            twos += 1

        # 2. Кандидати: непарні d з [3, L], d = 3 + 2*j, j = 0 .. C-1.
        limit = isqrt(m)
        count = (limit - 1) // 2 if limit >= 3 else 0

        # 3. Map: виклики асинхронні, тому всі воркери рахують одночасно.
        #    Числа передаємо рядками: так серіалізація Pyro4 однакова в Python 2 і 3.
        ranges = []
        mapped = []
        for i in range(n_workers):
            j_start = count * i // n_workers
            j_end = count * (i + 1) // n_workers
            lo = 3 + 2 * j_start          # перший кандидат діапазону
            hi = 3 + 2 * j_end            # перший кандидат ПІСЛЯ діапазону
            ranges.append((lo, hi, j_end - j_start))
            mapped.append(self.workers[i].mymap(str(m), str(lo), str(hi)))

        # 4. Reduce: чекаємо всіх воркерів і збираємо розклад.
        candidates, worker_results = self.myreduce(mapped)
        factors = [2] * twos + self.combine(m, candidates)

        elapsed = time.time() - t_start
        self.write_output(n, n_workers, limit, count, factors, elapsed, ranges, worker_results)
        print("Job Finished in %.3f s" % elapsed)

    @staticmethod
    @expose
    def mymap(m, lo, hi):
        """Виконується на воркері: непарні d з [lo, hi), що ділять m.
        Повертає (список дільників-рядків, секунди обчислень)."""
        t0 = time.time()
        found = Solver.trial_range(int(m), int(lo), int(hi))
        return [str(d) for d in found], time.time() - t0

    @staticmethod
    @expose
    def myreduce(mapped):
        candidates = []
        worker_results = []
        for future in mapped:
            divisors, seconds = future.value  # .value чекає завершення воркера
            divisors = [int(d) for d in divisors]
            candidates.extend(divisors)
            worker_results.append((divisors, seconds))
        return candidates, worker_results

    @staticmethod
    def trial_range(m, lo, hi):
        """Пробні дільники d = lo, lo+2, ..., < hi (lo непарне).
        Кожен знайдений дільник одразу вилучається з локальної копії m, тому складене d,
        утворене з простих цього ж діапазону, вже не спрацює. Складене d із простих
        МЕНШИХ за lo (з інших діапазонів) може потрапити в список - його відкидає combine."""
        found = []
        for d in range(lo, hi, 2):
            if m % d == 0:
                found.append(d)
                while m % d == 0:
                    m //= d
        return found

    @staticmethod
    def combine(m, candidates):
        """Канонічний розклад непарного m з кандидатів від воркерів.
        Кандидати перебираються за зростанням: кожне просте p <= L, що ділить m, є серед
        них, і до складеного кандидата всі його прості множники вже вилучені, тож воно
        більше не ділить залишок. Залишок > 1 - просте число, більше за L."""
        factors = []
        for d in sorted(set(candidates)):
            while m % d == 0:
                factors.append(d)
                m //= d
        if m > 1:
            factors.append(m)
        return factors

    @staticmethod
    def format_factors(factors):
        """[2, 2, 3, 7] -> '2^2 * 3 * 7'"""
        parts = []
        for p in sorted(set(factors)):
            e = factors.count(p)
            parts.append("%d^%d" % (p, e) if e > 1 else "%d" % p)
        return " * ".join(parts)

    def read_input(self):
        with io.open(self.input_file_name, 'r', encoding='utf-8') as f:
            lines = [line.strip() for line in f]
        lines = [line for line in lines if line and not line.startswith('#')]
        if len(lines) != 1:
            raise ValueError("Expected exactly one number N in the input file")
        n = int(lines[0])
        if n < 2:
            raise ValueError("N must be at least 2")
        return n

    def write_output(self, n, n_workers, limit, count, factors, elapsed, ranges, worker_results):
        product = 1
        for p in factors:
            product *= p
        with io.open(self.output_file_name, 'w', encoding='utf-8') as f:
            f.write(u"N: %d\n" % n)
            f.write(u"Workers: %d\n" % n_workers)
            f.write(u"Limit: %d\n" % limit)
            f.write(u"Candidates: %d\n" % count)
            f.write(u"Factorization: %s\n" % self.format_factors(factors))
            f.write(u"Check: %s\n" % ("OK" if product == n else "FAILED"))
            f.write(u"Total time: %.3f s\n" % elapsed)
            f.write(u"Worker compute times: %s\n"
                    % u", ".join(u"%.3f" % r[1] for r in worker_results))
            # номер, перший і останній кандидат, кількість кандидатів, секунди, дільники
            for i in range(n_workers):
                lo, hi, size = ranges[i]
                divisors, seconds = worker_results[i]
                last = hi - 2 if size > 0 else lo
                f.write(u"Worker %d: [%d, %d] %d %.3f %s\n"
                        % (i + 1, lo, last, size, seconds,
                           u" ".join(str(d) for d in divisors) or u"-"))
        print("output done")
