#!/usr/bin/env bash
# Deploy the current `main` to the server from this PC (Git Bash). The server
# never needs GitHub credentials: the code travels as a git archive over SSH.
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
rm -rf $ROOT/app.new && mkdir -p $ROOT/app.new
tar -xzf /tmp/mealtrack.tgz -C $ROOT/app.new
[ -d $ROOT/venv ] || python3 -m venv $ROOT/venv
$ROOT/venv/bin/pip install -q --upgrade pip
$ROOT/venv/bin/pip install -q -r $ROOT/app.new/requirements.txt
rm -rf $ROOT/app.old; [ -d $ROOT/app ] && mv $ROOT/app $ROOT/app.old; mv $ROOT/app.new $ROOT/app
chown -R mealtrack:mealtrack $ROOT/app $ROOT/venv
# hand model for the portion estimate (once)
MODEL=$ROOT/data/models/hand_landmarker.task
[ -f $MODEL ] || sudo -u mealtrack curl -sS -o $MODEL https://storage.googleapis.com/mediapipe-models/hand_landmarker/hand_landmarker/float16/1/hand_landmarker.task
cd $ROOT/app
set -a; source $ROOT/.env; set +a
sudo -u mealtrack -E $ROOT/venv/bin/alembic upgrade head
sudo -u mealtrack -E $ROOT/venv/bin/python scripts/import_foods.py
systemctl restart mealtrack
sleep 2; systemctl is-active mealtrack && curl -sf http://127.0.0.1:8000/health
EOF
echo "deployed to $HOST"
