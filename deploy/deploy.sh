#!/usr/bin/env bash
# Deploy the current `main` to the server from this PC (Git Bash). The server
# never needs GitHub credentials: the code travels as a git archive over SSH.
# First run on a fresh instance bootstraps it (packages, swap, user, venv);
# every run installs the code, migrates the database and restarts the service.
#   bash deploy/deploy.sh [host]
set -euo pipefail
HOST="${1:-meal.verenovotech.com}"
KEY="${MEALTRACK_SSH_KEY:-$HOME/.ssh/mealtrack.pem}"
SSH="ssh -i $KEY -o StrictHostKeyChecking=accept-new ubuntu@$HOST"

cd "$(dirname "$0")/.."
git archive --format=tar main | gzip > /tmp/mealtrack.tgz
scp -i "$KEY" -o StrictHostKeyChecking=accept-new /tmp/mealtrack.tgz ubuntu@$HOST:/tmp/mealtrack.tgz

$SSH 'sudo bash -s' <<'EOF'
set -euo pipefail
ROOT=/srv/mealtrack
export DEBIAN_FRONTEND=noninteractive

# --- bootstrap (idempotent) -------------------------------------------------
if ! command -v sqlite3 >/dev/null || ! dpkg -s python3-venv >/dev/null 2>&1; then
  apt-get update -q && apt-get install -y -q python3 python3-venv python3-pip sqlite3 unzip curl libgl1 libglib2.0-0
fi
if [ ! -f /swapfile ]; then  # 1 GB of RAM is enough for the app, but not for pip without swap
  fallocate -l 1G /swapfile && chmod 600 /swapfile && mkswap /swapfile >/dev/null && swapon /swapfile
  echo '/swapfile none swap sw 0 0' >> /etc/fstab
fi
id -u mealtrack >/dev/null 2>&1 || useradd --system --home $ROOT --shell /usr/sbin/nologin mealtrack
mkdir -p $ROOT/data/photos $ROOT/data/models $ROOT/data/cache
[ -f $ROOT/.env ] || { echo "missing $ROOT/.env (see deploy/env.production.example)"; exit 1; }

# --- code and dependencies --------------------------------------------------------
rm -rf $ROOT/app.new && mkdir -p $ROOT/app.new
tar -xzf /tmp/mealtrack.tgz -C $ROOT/app.new
[ -d $ROOT/venv ] || python3 -m venv $ROOT/venv
$ROOT/venv/bin/pip install -q --upgrade pip
$ROOT/venv/bin/pip install -q -r $ROOT/app.new/requirements.txt
rm -rf $ROOT/app.old; [ -d $ROOT/app ] && mv $ROOT/app $ROOT/app.old; mv $ROOT/app.new $ROOT/app
MODEL=$ROOT/data/models/hand_landmarker.task   # hand model for the portion estimate (once)
[ -f $MODEL ] || curl -sS -o $MODEL https://storage.googleapis.com/mediapipe-models/hand_landmarker/hand_landmarker/float16/1/hand_landmarker.task
chown -R mealtrack:mealtrack $ROOT
chmod 600 $ROOT/.env

# --- database and foods -------------------------------------------------------------
cd $ROOT/app
set -a; source $ROOT/.env; set +a
sudo -u mealtrack -E $ROOT/venv/bin/alembic upgrade head
sudo -u mealtrack -E $ROOT/venv/bin/python scripts/import_foods.py

# --- service (installed by setup.sh; restart if present) ----------------------------
if systemctl list-unit-files mealtrack.service >/dev/null 2>&1 && [ -f /etc/systemd/system/mealtrack.service ]; then
  systemctl restart mealtrack
  sleep 2; systemctl is-active mealtrack && curl -sf http://127.0.0.1:8000/health && echo
fi
EOF
echo "deployed to $HOST"
