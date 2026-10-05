#!/usr/bin/env bash
# Server setup after the first deploy.sh: nginx, HTTPS, the service, the backup cron.
# Run once on the server as root, when the DNS record points at it:
#   sudo bash /srv/mealtrack/app/deploy/setup.sh meal.verenovotech.com afguida@gmail.com
# Idempotent: safe to run again.
set -euo pipefail

DOMAIN="${1:?domain}"
EMAIL="${2:?email for Let's Encrypt}"
ROOT=/srv/mealtrack
APP=$ROOT/app
DATA=$ROOT/data
export DEBIAN_FRONTEND=noninteractive

apt-get update -q
apt-get install -y -q nginx certbot python3-certbot-nginx

# AWS CLI for the backups (Ubuntu's package is old; the official bundle is fine).
if ! command -v aws >/dev/null; then
  curl -sS "https://awscli.amazonaws.com/awscli-exe-linux-$(uname -m).zip" -o /tmp/awscli.zip
  unzip -q -o /tmp/awscli.zip -d /tmp && /tmp/aws/install --update >/dev/null && rm -rf /tmp/aws /tmp/awscli.zip
fi

# systemd service
install -m 644 $APP/deploy/mealtrack.service /etc/systemd/system/mealtrack.service
systemctl daemon-reload
systemctl enable mealtrack
systemctl restart mealtrack

# nginx site (plain HTTP first, so certbot can answer the challenge)
sed "s/__DOMAIN__/$DOMAIN/g" $APP/deploy/nginx.conf > /etc/nginx/sites-available/mealtrack
ln -sf /etc/nginx/sites-available/mealtrack /etc/nginx/sites-enabled/mealtrack
rm -f /etc/nginx/sites-enabled/default
nginx -t && systemctl reload nginx

# HTTPS (certbot edits the nginx site, adds the redirect and the renewal timer)
if [ ! -d /etc/letsencrypt/live/$DOMAIN ]; then
  certbot --nginx --non-interactive --agree-tos -m "$EMAIL" -d "$DOMAIN" --redirect
fi

# weekly backup (Sunday 03:30) and its log
install -m 755 $APP/deploy/backup.sh /usr/local/bin/mealtrack-backup
echo "30 3 * * 0 mealtrack /usr/local/bin/mealtrack-backup >> $DATA/backup.log 2>&1" > /etc/cron.d/mealtrack-backup
touch $DATA/backup.log && chown mealtrack:mealtrack $DATA/backup.log

sleep 2; systemctl is-active mealtrack && curl -sf http://127.0.0.1:8000/health && echo
echo "setup done: https://$DOMAIN"
