# Deployment (AWS, eu-west-1)

One small instance runs the app and its SQLite database; S3 keeps photos and the
weekly backups. Everything is scripted here so the server can be rebuilt from
scratch. Commands are run from the PC in Git Bash unless stated otherwise.

## Pieces

| What | Where | Why |
| --- | --- | --- |
| EC2 `t3a.micro`, Ubuntu 24.04, 12 GB gp3, fixed IPv4 | `provision.sh` | app + DB + hand model; ~7 $/month + ~1.2 $ disk + ~3.7 $ IPv4 |
| Security group `mealtrack` | `provision.sh` | 80/443 open, SSH only from the home IP |
| S3 bucket `mealtrack-<account>` | `provision.sh`, `s3-lifecycle.json` | versioning on, public access blocked, `backups/` deleted after 60 days |
| IAM role `mealtrack-instance` | `provision.sh`, `iam-instance-policy.json` | the instance may touch that bucket only |
| DNS `meal.verenovotech.com` | `provision.sh` | A record in the Route 53 zone |
| AWS Budget `mealtrack-monthly` | `provision.sh` | email at 80 % of 15 $ actual, 100 % forecast |
| nginx + Let's Encrypt | `setup.sh`, `nginx.conf` | HTTPS, static files, 15 MB uploads |
| systemd `mealtrack.service` | `setup.sh`, `mealtrack.service` | uvicorn on 127.0.0.1:8000, restarts on failure |
| Weekly backup | `setup.sh`, `backup.sh` | Sunday 03:30: SQLite `.backup` → S3, photos synced |
| Schema migrations | `../migrations/` (Alembic) | `deploy.sh` runs `alembic upgrade head` |

## First deployment

1. `winget install Amazon.AWSCLI`, `aws configure` as the IAM user `mealtrack-deploy` (region `eu-west-1`).
   On a PC where an antivirus intercepts HTTPS, point the CLI at a bundle that includes its certificate
   (`AWS_CA_BUNDLE=...`), see the note at the end.
2. `MY_IP=<your public IPv4> bash deploy/provision.sh` — prints the instance IP.
3. Wait two minutes, then create the server's `.env` from `env.production.example` with a real
   `SECRET_KEY` (`python -c "import secrets; print(secrets.token_urlsafe(48))"`):
   ```
   ssh -i ~/.ssh/mealtrack.pem ubuntu@<ip> 'sudo mkdir -p /srv/mealtrack && sudo tee /srv/mealtrack/.env >/dev/null' < my.env
   ```
4. `bash deploy/deploy.sh <ip>` — bootstrap (packages, swap, user), code, venv, migrations, foods.
5. On the server: `sudo bash /srv/mealtrack/app/deploy/setup.sh meal.verenovotech.com afguida@gmail.com` — service, nginx, certificate, backup cron.
6. Open https://meal.verenovotech.com from a phone and **register** (`ALLOW_SIGNUP=true`): no user is seeded on the server.
   Set `ALLOW_SIGNUP=false` in `.env` and `sudo systemctl restart mealtrack` once the family is in.

## Every later release

```
bash deploy/deploy.sh
```
(archives `main`, uploads, installs, migrates, restarts; ~1 minute.)

## Backups

- Weekly, automatic; check `/srv/mealtrack/data/backup.log` or `aws s3 ls s3://mealtrack-<account>/backups/`.
- Manual: `sudo -u mealtrack /usr/local/bin/mealtrack-backup`.
- Restore test: `aws s3 cp s3://.../backups/mealtrack-YYYY-MM-DD.db /tmp/r.db && sqlite3 /tmp/r.db "PRAGMA integrity_check; select count(*) from meals;"`.
  To restore for real: stop the service, replace `/srv/mealtrack/data/mealtrack.db`, start it.

## Costs

About 12 $/month (figures from memory, 2026-10; check the AWS calculator). Nothing is billed per user or per photo.
Any change that raises this (bigger instance, a second one, a paid API) is to be flagged before it is made.
The budget alert emails afguida@gmail.com before the month ends above 15 $.

## Note: antivirus HTTPS interception

Norton on the development PC re-signs HTTPS traffic. The AWS CLI then fails with
`CERTIFICATE_VERIFY_FAILED`. Fix for a session: build a bundle of the CLI's CA list plus
`C:\ProgramData\Norton\Antivirus\wscert.pem` and set `AWS_CA_BUNDLE` to it (or
`aws configure set ca_bundle <path>` to make it permanent).
