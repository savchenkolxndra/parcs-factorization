#!/usr/bin/env bash
# Серія замірів на кластері PARCS: послідовна версія та паралельна для різної кількості воркерів.
#
# Запуск:  bash tools/run_measurements.sh MASTER_URL INPUT RESULT_DIR [RUNS] ["WORKER_COUNTS"]
# Приклад: bash tools/run_measurements.sh http://34.118.1.2:8080 input/semiprime_62bit.txt results/semiprime_62bit 3 "1 2 4"
#
# Послідовна версія надсилається як звичайна задача PARCS і виконується на майстрі
# (та сама VM і той самий Python 2.7, що й у воркерів). Кількість воркерів змінюється
# через API майстра: зайві вимикаються, тож кластер не треба перестворювати.
# Результат: RESULT_DIR/results.csv і вихідні файли кожної задачі.
set -u

MASTER=${1:?MASTER_URL}
INPUT=${2:?INPUT}
OUT=${3:?RESULT_DIR}
RUNS=${4:-3}
COUNTS=${5:-"1 2 4"}
PARALLEL=solution/factorization_parallel.py
SEQUENTIAL=solution/factorization_sequential.py
TIMEOUT=1800   # секунд на одну задачу

if [ -e "$OUT/results.csv" ]; then
    echo "$OUT/results.csv already exists - choose a new RESULT_DIR so runs do not mix"; exit 1
fi
mkdir -p "$OUT"
CSV="$OUT/results.csv"
echo "mode,workers,run,job_id,factorization,check,total_time_s,worker_times_s" > "$CSV"

api() { curl -fsS --max-time 30 "$@"; }

worker_ids() {
    api "$MASTER/api/worker" | tr ',{' '\n\n' | sed -n 's/^ *"id": *\([0-9]*\).*/\1/p' | sort -n
}

# Вмикає перших N воркерів, решту вимикає.
use_workers() {
    local want=$1 used=0 id state
    for id in $(worker_ids); do
        if [ "$used" -lt "$want" ]; then state=enable; used=$((used + 1)); else state=disable; fi
        api -o /dev/null -X POST "$MASTER/api/worker/$id/$state" || return 1
    done
    [ "$used" -eq "$want" ] || { echo "Only $used workers are registered, $want needed"; return 1; }
}

# PARCS нумерує задачі по порядку з нуля: наступний номер = останній + 1.
last=$(api "$MASTER/jobs" | grep -o '/api/job/[0-9]*/' | grep -o '[0-9]\+' | sort -n | tail -1)
next_job=$(( ${last:--1} + 1 ))

# run_job MODE WORKERS RUN SOLUTION
run_job() {
    local mode=$1 workers=$2 run=$3 solution=$4 job=$next_job file code start
    next_job=$((next_job + 1))
    api -o /dev/null -F "job_name=${mode}_w${workers}_r${run}" \
        -F "solution_file=@$solution" -F "input_file=@$INPUT" "$MASTER/api/job" \
        || { echo "Submit failed"; exit 1; }
    file="$OUT/output_${mode}_w${workers}_r${run}.txt"
    start=$SECONDS
    while :; do   # 200 - готово, 400 - ще рахується
        code=$(curl -sS --max-time 60 -o "$file" -w '%{http_code}' "$MASTER/api/job/$job/output")
        [ "$code" = 200 ] && break
        [ "$code" = 400 ] || { echo "Job $job failed (http $code), see $MASTER/jobs"; exit 1; }
        [ $((SECONDS - start)) -lt $TIMEOUT ] || { echo "Job $job timed out"; exit 1; }
        sleep 2
    done
    field() { sed -n "s/^$1: *//p" "$file" | head -1; }
    if [ "$mode" = parallel ] && [ "$(field Workers)" != "$workers" ]; then
        echo "Job $job used $(field Workers) workers instead of $workers"; exit 1
    fi
    echo "$mode,$workers,$run,$job,\"$(field Factorization)\",$(field Check),$(field 'Total time' | sed 's/ s$//'),\"$(field 'Worker compute times')\"" >> "$CSV"
    echo "$mode workers=$workers run=$run job=$job time=$(field 'Total time') [$(field Check)] $(field Factorization)"
}

use_workers 1 || exit 1
for run in $(seq 1 "$RUNS"); do run_job sequential 0 "$run" "$SEQUENTIAL"; done

for workers in $COUNTS; do
    use_workers "$workers" || exit 1
    for run in $(seq 1 "$RUNS"); do run_job parallel "$workers" "$run" "$PARALLEL"; done
done

use_workers "$(worker_ids | wc -l)"   # повертаємо всіх воркерів
echo "DONE -> $CSV"
echo "Table and chart: python3 tools/summarize.py $CSV"
