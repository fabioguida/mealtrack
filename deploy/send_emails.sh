#!/usr/bin/env bash
# Cron wrapper: load the server's .env and run the email sender.
#   mealtrack-send daily | weekly
set -euo pipefail
set -a; source /srv/mealtrack/.env; set +a
cd /srv/mealtrack/app
exec /srv/mealtrack/venv/bin/python scripts/send_emails.py "$@"
