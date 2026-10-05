#!/usr/bin/env bash
# First-time setup of the server (Ubuntu 24.04). Run once as root, after the
# instance is up and the DNS record points at it:
#   sudo bash /srv/mealtrack/app/deploy/setup.sh meal.verenovotech.com afguida@gmail.com
# Idempotent: safe to run again.
set -euo pipefail

DOMAIN="${1:?domain}"
EMAIL="${2:?email for Let's Encrypt}"
ROOT=/srv/mealtrack
APP=$ROOT/app
DATA=$ROOT/data

apt-get update -q
DEBIAN_FRONTEND=noninteractive apt-get install -y -q python3 python3-venv python3-pip nginx certbot python3-certbot-nginx sqlite3 unzip libgl1 libglib2.0-0

# 1 GB swap: the hand model and OpenCV fit in 1 GB of RAM, but with no margin.
if [ ! -f /swapfile ]; then
  fallocate -l 1G /swapfile && chmod 600 /swapfile && mkswap /swapfile && swapon /swapfile
  echo '/swapfile none swap sw 0 0' >> /etc/fstab
fi

id -u mealtrack >/dev/null 2>&1 || useradd --system --home $ROOT --shell /usr/sbin/nologin mealtrack
mkdir -p $APP $DATA/photos $DATA/models $DATA/cache
chown -R mealtrack:mealtrack $ROOT

# AWS CLI for the backups (Ubuntu's package is old; the official bundle is fine).
if ! command -v aws >/dev/null; then
  curl -sS "https://awscli.amazonaws.com/awscli-exe-linux-$(uname -m).zip" -o /tmp/awscli.zip
  unzip -q -o /tmp/awscli.zip -d /tmp && /tmp/aws/install --update >/dev/null && rm -rf /tmp/aws /tmp/awscli.zip
fi

# systemd service and nginx site
install -m 644 $APP/deploy/mealtrack.service /etc/systemd/system/mealtrack.service
sed "s/__DOMAIN__/$DOMAIN/g" $APP/deploy/nginx.conf > /etc/nginx/sites-available/mealtrack
ln -sf /etc/nginx/sites-available/mealtrack /etc/nginx/sites-enabled/mealtrack
rm -f /etc/nginx/sites-enabled/default
nginx -t && systemctl reload nginx

# weekly backup (Sunday 03:30) and the log
install -m 755 $APP/deploy/backup.sh /usr/local/bin/mealtrack-backup
echo "30 3 * * 0 mealtrack /usr/local/bin/mealtrack-backup >> $DATA/backup.log 2>&1" > /etc/cron.d/mealtrack-backup

systemctl daemon-reload
systemctl enable mealtrack

# HTTPS (certbot edits the nginx site and sets up renewal)
if [ ! -d /etc/letsencrypt/live/$DOMAIN ]; then
  certbot --nginx --non-interactive --agree-tos -m "$EMAIL" -d "$DOMAIN" --redirect
fi
echo "setup done: now run deploy/deploy.sh from your PC"
