#!/usr/bin/env bash
# Видаляє лише VM цього кластера (fact-master, fact-worker*, мітка lab=fact-parcs) разом із дисками
# та правило firewall fact-parcs-web. Інші VM у проєкті не зачіпаються.
# Запуск:  bash tools/gcp_down.sh PROJECT_ID [ZONE=europe-central2-a]
set -uo pipefail

PROJECT=${1:?PROJECT_ID}
ZONE=${2:-europe-central2-a}
G="gcloud --project=$PROJECT --quiet"
P=fact

VMS=$($G compute instances list --filter=labels.lab=$P-parcs --format='value(name)')
if [ -n "$VMS" ]; then
    $G compute instances delete $VMS --zone="$ZONE" --delete-disks=all
fi
$G compute firewall-rules delete $P-parcs-web 2>/dev/null

LEFT=$($G compute instances list --filter=labels.lab=$P-parcs --format='value(name)')
if [ -n "$LEFT" ]; then
    echo "WARNING: still running (and billed): $LEFT"; exit 1
fi
echo "All PARCS VMs are deleted."
