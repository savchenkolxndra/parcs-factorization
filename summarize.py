# -*- coding: utf-8 -*-
"""
Таблиця середніх часів, прискорення S(k) = T_посл / T(k), ефективності E(k) = S(k) / k
і графік прискорення за файлом results.csv, який створює run_measurements.sh.

Запуск:  python3 tools/summarize.py results/semiprime_62bit/results.csv
Графік (speedup.png поруч із CSV) малюється, якщо встановлено matplotlib.
"""
import csv
import os
import sys
from collections import defaultdict


def main():
    path = sys.argv[1]
    times = defaultdict(list)
    with open(path, encoding="utf-8") as f:
        for row in csv.DictReader(f):
            if row["check"] != "OK":
                print("WARNING: job %s has check=%s" % (row["job_id"], row["check"]))
            times[(row["mode"], int(row["workers"]))].append(float(row["total_time_s"]))

    seq = times.get(("sequential", 0))
    if not seq:
        sys.exit("No sequential runs in the CSV")
    t_seq = sum(seq) / len(seq)

    def fmt(x):
        return ("%.2f" % x).replace(".", ",")   # десяткова кома, як у звіті

    print("Конфігурація;Прогони, с;Середній час, с;Прискорення S;Ефективність E")
    print("Послідовна версія;%s;%s;1,00;-" % (" / ".join(fmt(t) for t in seq), fmt(t_seq)))
    ks, speedups = [], []
    for (mode, k) in sorted(key for key in times if key[0] == "parallel"):
        runs = times[(mode, k)]
        t = sum(runs) / len(runs)
        s = t_seq / t
        ks.append(k)
        speedups.append(s)
        print("PARCS, воркерів: %d;%s;%s;%s;%d %%"
              % (k, " / ".join(fmt(x) for x in runs), fmt(t), fmt(s), round(100 * s / k)))

    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except ImportError:
        print("(matplotlib is not installed - no chart)")
        return
    fig, ax = plt.subplots(figsize=(6, 4))
    ax.plot(ks, ks, "--", color="gray", label="Ідеальне (лінійне)")
    ax.plot(ks, speedups, "o-", color="#1f6feb", label="Отримане")
    for k, s in zip(ks, speedups):
        ax.annotate(fmt(s), (k, s), textcoords="offset points", xytext=(0, 8), ha="center")
    ax.set_xlabel("Кількість воркерів k")
    ax.set_ylabel("Прискорення S(k)")
    ax.set_xticks(ks)
    ax.grid(alpha=0.3)
    ax.legend()
    fig.tight_layout()
    out = os.path.join(os.path.dirname(path), "speedup.png")
    fig.savefig(out, dpi=150)
    print("Chart:", out)


if __name__ == "__main__":
    main()
