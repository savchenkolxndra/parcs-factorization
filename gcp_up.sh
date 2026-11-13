#!/usr/bin/env bash
# Створює кластер PARCS-Python у Google Cloud: майстер + N воркерів (Docker-образ hummer12007/parcs-node).
# Зручно запускати з Google Cloud Shell (там уже є gcloud).
#
# Запуск:  bash tools/gcp_up.sh PROJECT_ID [WORKERS=4] [ZONE=europe-central2-a] [EXTRA_IP]
#   EXTRA_IP - публічна IP твого ПК (https://ifconfig.me), щоб відкрити веб-інтерфейс у браузері.
#   Адреса машини, з якої запущено скрипт (наприклад, Cloud Shell), дозволяється автоматично.
#
# VM КОШТУЮТЬ ГРОШЕЙ, поки існують. Після замірів обов'язково: bash tools/gcp_down.sh PROJECT_ID
set -euo pipefail

PROJECT=${1:?PROJECT_ID}
WORKERS=${2:-4}
ZONE=${3:-europe-central2-a}
EXTRA_IP=${4:-}
MACHINE=n1-standard-1           # 1 vCPU, 3,75 ГБ - однакові VM для всіх вузлів
IMAGE=registry.hub.docker.com/hummer12007/parcs-node
# Унікальні імена: кластер не перетинається з чужими VM у спільному проєкті.
P=fact
G="gcloud --project=$PROJECT --quiet"

if [ -n "$($G compute instances list --filter=labels.lab=$P-parcs --format='value(name)')" ]; then
    echo "Cluster $P-* already exists. Run tools/gcp_down.sh first."; exit 1
fi

MY_IP=$(curl -fsS --max-time 15 https://checkip.amazonaws.com | tr -d '[:space:]')
SOURCES="$MY_IP/32"
[ -n "$EXTRA_IP" ] && SOURCES="$SOURCES,$EXTRA_IP/32"
echo "Port 8080 will be open only for: $SOURCES"

$G services enable compute.googleapis.com

# PARCS виконує будь-який надісланий код без пароля, тому порт 8080 - лише для твоїх адрес.
# Обмін між VM дозволяє стандартне правило default-allow-internal (його скрипт не змінює).
if $G compute firewall-rules describe $P-parcs-web >/dev/null 2>&1; then
    $G compute firewall-rules update $P-parcs-web --source-ranges="$SOURCES"
else
    $G compute firewall-rules create $P-parcs-web --network=default --direction=INGRESS \
        --action=ALLOW --rules=tcp:8080 --source-ranges="$SOURCES" --target-tags=$P-parcs-master
fi

# Стартовий скрипт VM: запускає контейнер PARCS у мережі хоста.
startup() {
    cat <<EOF
#!/bin/bash
iptables -w -A INPUT -p tcp -j ACCEPT
docker rm -f parcs 2>/dev/null
docker run -d --name parcs --restart=always --network host -e PARCS_ARGS="$1" $IMAGE
EOF
}

create_vm() {  # NAME PARCS_ARGS TAG
    local tmp; tmp=$(mktemp)
    startup "$2" > "$tmp"
    $G compute instances create "$1" --zone="$ZONE" --machine-type=$MACHINE \
        --image-family=cos-stable --image-project=cos-cloud --boot-disk-size=10GB \
        --no-service-account --no-scopes --tags="$3" --labels=lab=$P-parcs \
        --metadata-from-file=startup-script="$tmp"
    rm -f "$tmp"
}

create_vm $P-master master $P-parcs-master
MASTER_INTERNAL=$($G compute instances describe $P-master --zone="$ZONE" --format='get(networkInterfaces[0].networkIP)')
MASTER_EXTERNAL=$($G compute instances describe $P-master --zone="$ZONE" --format='get(networkInterfaces[0].accessConfigs[0].natIP)')

for i in $(seq 1 "$WORKERS"); do
    create_vm "$P-worker$i" "worker $MASTER_INTERNAL" $P-parcs-worker
done

echo
echo "Master: http://$MASTER_EXTERNAL:8080  (ready in ~2-3 minutes)"
echo "Check that all $WORKERS workers are registered: http://$MASTER_EXTERNAL:8080/workers"
echo "Measurements: bash tools/run_measurements.sh http://$MASTER_EXTERNAL:8080 input/semiprime_62bit.txt results/semiprime_62bit 3 \"1 2 4\""
echo "DON'T FORGET: bash tools/gcp_down.sh $PROJECT $ZONE"
