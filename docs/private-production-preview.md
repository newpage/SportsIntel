# Private Linux production preview runbook

This package prepares a manually reviewed, single-host private preview. It does
not deploy automatically. Supported hosts are current Ubuntu LTS and Debian
stable releases with Docker Engine, Docker Compose v2, Apache 2.4, Git, curl,
`apache2-utils`, and PostgreSQL client tools.

## Architecture and sizing

Apache is the only public process. It terminates HTTPS and Basic Authentication,
then proxies `/api/` and `/health` to FastAPI on `127.0.0.1:8300` and all other
traffic to Next.js on `127.0.0.1:3300`. PostgreSQL has no published host port and
is reachable only on the internal database network. Named volumes retain
PostgreSQL and legacy prediction-history data across releases.

Start with 2 vCPU, 4 GB RAM, and 40 GB SSD, plus encrypted backup storage sized
for at least 14 daily database dumps. Monitor actual CPU, memory, database growth,
Docker image use, and free disk before resizing. The Compose file intentionally
does not impose tight resource limits during the preview.

## Prerequisites, DNS, and firewall

Create an A/AAAA record for `<PREVIEW_DOMAIN>` pointing to `<SERVER_ADDRESS>`.
Allow inbound 443, inbound 80 for ACME/redirects, and SSH only from approved
administration networks. Deny public 3000, 3300, 8000, 8300, and 5432. Confirm CI
is green for the exact commit before deployment.

```bash
git clone <REPOSITORY_URL> /tmp/sportsintel-bootstrap
cd /tmp/sportsintel-bootstrap
deploy/linux/install.sh --check-only
sudo deploy/linux/install.sh
sudo -u sportsintel git clone <REPOSITORY_URL> /opt/sportsintel/app
cd /opt/sportsintel/app
```

The install script reports missing packages and planned directory changes. It
does not alter Apache or firewall rules. Docker-group access is root-equivalent.

## Production environment and secrets

```bash
sudo install -o root -g sportsintel -m 0640 production.env.example \
  /opt/sportsintel/shared/production.env
sudoedit /opt/sportsintel/shared/production.env
openssl rand -base64 48
openssl rand -base64 36
```

Replace `<PREVIEW_DOMAIN>`, database password, and admin key placeholders. Keep
the admin API key separate from Basic Auth. `DATABASE_URL` must match the
PostgreSQL variables. Never commit the environment file or expose it in logs.
The deployment script generates commit, version, build time, and production mode
in `/opt/sportsintel/shared/release.env`; operators do not edit those values.
`SPORTSINTEL_INTERNAL_API_URL=http://api:8000` is consumed only by Next.js server
components on the private application network. `NEXT_PUBLIC_API_URL=/api` is the
browser-safe same-origin prefix routed by Apache. Never expose `api:8000` through
a `NEXT_PUBLIC_*` variable or substitute it into client bundles.

## Apache, authentication, and HTTPS

```bash
sudo a2enmod proxy proxy_http proxy_wstunnel headers ssl rewrite auth_basic
sudo cp deploy/apache/sportsintel.conf.example \
  /etc/apache2/sites-available/sportsintel.conf
sudo deploy/apache/create-preview-user.sh <PREVIEW_USERNAME>
sudo a2ensite sportsintel.conf
sudo apache2ctl configtest
sudo systemctl reload apache2
sudo certbot --apache -d <PREVIEW_DOMAIN>
```

Edit the site template first to replace `sports.example.com`. Certbot or the
organization certificate process must provide valid certificate paths. Verify
renewal with `sudo certbot renew --dry-run`. Apache logs are
`/var/log/apache2/sportsintel-access.log` and `sportsintel-error.log`. The entire
external site, including health, remains authenticated; loopback health stays
available to local monitoring. The template allows 10 MB requests and a
60-second proxy timeout—raise these only after reviewing operational impact.

## First deployment and schema

Deploy an immutable reviewed SHA or signed/reviewed tag, never a dirty checkout:

```bash
sudo -u sportsintel /opt/sportsintel/app/deploy/linux/deploy.sh <RELEASE_SHA_OR_TAG>
sudo -u sportsintel /opt/sportsintel/app/deploy/linux/status.sh
```

The release process fetches the ref, records the previous commit, builds images,
starts PostgreSQL, reapplies the idempotent schema, updates services, waits for
health, runs internal smoke tests, and atomically writes
`/opt/sportsintel/shared/deployment.json`. A failure stops metadata promotion and
prints the failed validation; inspect `docker compose ... logs` before retrying.

For external acceptance:

```bash
export SPORTSINTEL_PUBLIC_URL=https://<PREVIEW_DOMAIN>
export SPORTSINTEL_PREVIEW_USER=<PREVIEW_USERNAME>
read -rs SPORTSINTEL_PREVIEW_PASSWORD; export SPORTSINTEL_PREVIEW_PASSWORD
deploy/linux/smoke-test.sh --external
unset SPORTSINTEL_PREVIEW_PASSWORD
```

External smoke testing first requires an unauthenticated `401`, then verifies
that authenticated HTTPS returns server-rendered NFL Command Center content.
`SPORTSINTEL_SMOKE_INSECURE=true` exists only for disposable self-signed local/CI
rehearsals and must not be used for the real preview certificate.

## Status, monitoring, and logs

```bash
deploy/linux/status.sh
docker compose --env-file /opt/sportsintel/shared/release.env \
  -f docker-compose.production.yml logs --tail=200 api web postgres
```

Status shows release metadata, container/health state, persistent snapshot count,
disk use, and container state without reading or printing environment secrets.
Install the health timer by copying both health unit files to `/etc/systemd/system`,
then run `sudo systemctl daemon-reload && sudo systemctl enable --now sportsintel-health.timer`.
Failures appear in `journalctl -u sportsintel-health.service`; future alerting can
consume its nonzero exit without storing external alert credentials here.

## Backup, restore, and scheduling

```bash
deploy/linux/backup.sh
sudo cp deploy/systemd/sportsintel-backup.* /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now sportsintel-backup.timer
sudo systemctl list-timers 'sportsintel-*'
```

Backups are timestamped custom-format dumps, written atomically with mode 0600,
and retained for `SPORTSINTEL_BACKUP_RETENTION_DAYS` (14 by default). Store an
encrypted off-host copy. Rehearse restores regularly on an isolated host.

```bash
deploy/linux/restore.sh /opt/sportsintel/backups/<APPROVED_BACKUP>.dump
# Noninteractive only after explicit operator review:
deploy/linux/restore.sh /opt/sportsintel/backups/<APPROVED_BACKUP>.dump --yes
```

Restore validates the archive, makes a pre-restore backup, stops dependents,
restores PostgreSQL, restarts the stack, and runs smoke tests.

## Upgrade and rollback

```bash
git fetch --tags origin
deploy/linux/backup.sh
deploy/linux/deploy.sh <NEW_REVIEWED_SHA_OR_TAG>
deploy/linux/rollback.sh
```

Rollback uses `previous_release_commit`, preserves PostgreSQL data, rebuilds the
prior application, and verifies health. Database-destructive migrations need a
separate compatibility and restore plan; Sprint 14.10 contains none.

## Troubleshooting

- Startup validation: inspect `docker compose ... logs api` without printing the
  environment file.
- 502/503: check `status.sh`, API/web health, then Apache error logs.
- Database failure: confirm the internal network, volume, credentials, disk, and
  snapshot-store health endpoint.
- Authentication failure: recreate the preview user and run `apache2ctl configtest`.
- Certificate failure: confirm DNS, port 80/443 policy, certificate paths, and renewal.
- Disk pressure: preserve backups first, then prune unused Docker images; never
  delete the PostgreSQL volume as routine cleanup.

## Complete removal

After written approval and verified off-host backups:

```bash
docker compose --env-file /opt/sportsintel/shared/release.env \
  -f docker-compose.production.yml down
sudo a2dissite sportsintel.conf && sudo systemctl reload apache2
sudo systemctl disable --now sportsintel-backup.timer sportsintel-health.timer
```

This preserves volumes and backups. Destructive removal of volumes,
`/opt/sportsintel`, credentials, certificates, or backups is a separate approved
operation and cannot be recovered locally.

## Preview acceptance checklist

- [ ] CI is green for the deployed commit.
- [ ] HTTPS certificate and redirect are valid.
- [ ] Basic Authentication is enforced before all preview content.
- [ ] NFL Command Center and game details load.
- [ ] NFL API functions and MLB responds without blocking NFL.
- [ ] PostgreSQL snapshot persistence reports healthy.
- [ ] Snapshot history survives a container restart.
- [ ] Destructive history endpoints reject missing admin keys.
- [ ] A restricted backup was created and a restore rehearsed.
- [ ] Application rollback was rehearsed.
- [ ] PostgreSQL has no public listener.
- [ ] Prediction behavior and outputs are unchanged.
