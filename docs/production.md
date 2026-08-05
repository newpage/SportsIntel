# SportsIntel production deployment

For the complete private-preview release, authentication, backup, restore, and
rollback workflow, use [private-production-preview.md](private-production-preview.md).
The guidance below remains a concise description of the application runtime.

This guide describes the first supported Linux deployment: Docker Compose on a
single host, PostgreSQL in the Compose stack, and Apache terminating HTTPS. The
API and web ports remain bound to loopback; only Apache is internet-facing.

## Host preparation

Use a maintained Linux release with Docker Engine, the Compose plugin, Apache
2.4, `mod_proxy`, `mod_proxy_http`, `mod_headers`, and a firewall. Create a
dedicated deployment account, clone the repository under `/opt/sportsintel`, and
limit write access to that account. Membership in the Docker group is equivalent
to root access and must be restricted accordingly.

```bash
sudo install -d -o sportsintel -g sportsintel /opt/sportsintel
cd /opt/sportsintel
git clone https://github.com/newpage/SportsIntel.git app
cd app
cp production.env.example .env
sudo chown root:sportsintel .env
sudo chmod 640 .env
sudo chown -R 10001:10001 data
```

Replace every placeholder in `.env`. Generate the admin key and database
password with a cryptographically secure password generator. Production startup
fails when required variables are missing, placeholder-like, insecure, or when
the snapshot store is not PostgreSQL.

## Environment variables

| Variable | Required in production | Purpose |
| --- | --- | --- |
| `API_PORT` | Yes | Loopback host port published for FastAPI. |
| `WEB_PORT` | Yes | Loopback host port published for Next.js. |
| `NEXT_PUBLIC_API_URL` | Yes | Public HTTPS API origin used by the web build/runtime. |
| `SPORTSINTEL_ENV` | Yes | Must be `production` for production validation and HSTS. |
| `SPORTSINTEL_VERSION` | Yes | Release version returned by `/health`. |
| `SPORTSINTEL_BUILD_TIMESTAMP` | Yes | Timezone-aware ISO-8601 build/deploy timestamp. |
| `SPORTSINTEL_GIT_COMMIT` | Yes | Deployed Git commit returned by `/health`. |
| `SPORTSINTEL_ADMIN_KEY` | Yes | Random key of at least 32 characters for administrative routes. |
| `SPORTSINTEL_CORS_ORIGINS` | Yes | Comma-separated HTTPS browser origins; wildcards are rejected. |
| `SPORTSINTEL_PUBLIC_RATE_LIMIT` | Yes | Public requests allowed per minute per client IP. |
| `SPORTSINTEL_ADMIN_RATE_LIMIT` | Yes | Administrative requests allowed per minute per client IP. |
| `SPORTSINTEL_TRUST_PROXY_HEADERS` | Yes behind Apache | Trust the last `X-Forwarded-For` address for logging/limits. Enable only behind the trusted loopback proxy. |
| `YAHOO_NFL_RSS_URL` | No | Yahoo NFL feed URL. |
| `PREDICTION_HISTORY_FILE` | Yes | In-container path for the existing JSON prediction history. |
| `NFL_SNAPSHOT_STORE` | Yes | Must be `postgres` in production. |
| `DATABASE_URL` | Yes | PostgreSQL connection URL used only by the API. Never log it. |
| `POSTGRES_DB` | Yes | Database created by the PostgreSQL container. |
| `POSTGRES_USER` | Yes | PostgreSQL application role. |
| `POSTGRES_PASSWORD` | Yes | PostgreSQL password; must match `DATABASE_URL`. |

Before each deployment, set `SPORTSINTEL_BUILD_TIMESTAMP` to the current UTC
time and `SPORTSINTEL_GIT_COMMIT` to the exact reviewed commit. Keep `.env` out
of source control and never paste it into tickets or logs.

## Deploy

```bash
git fetch --tags origin
git checkout <reviewed-commit-or-tag>
docker compose config --quiet
docker compose build --pull api web
docker compose up -d
docker compose ps
```

The containers run as non-root application users, receive `SIGTERM`, and have
grace periods for shutdown. Compose restarts services unless explicitly stopped.
PostgreSQL, API, and web healthchecks gate dependent startup.

## Apache reverse proxy and HTTPS

Enable the required modules:

```bash
sudo a2enmod proxy proxy_http headers ssl rewrite
```

Use a virtual host like the following, replacing the hostname. The API and web
ports remain accessible only from `127.0.0.1`.

```apache
<VirtualHost *:80>
    ServerName sports.example.com
    Redirect permanent / https://sports.example.com/
</VirtualHost>

<VirtualHost *:443>
    ServerName sports.example.com
    SSLEngine on
    SSLCertificateFile /etc/letsencrypt/live/sports.example.com/fullchain.pem
    SSLCertificateKeyFile /etc/letsencrypt/live/sports.example.com/privkey.pem

    ProxyPreserveHost On
    RequestHeader set X-Forwarded-Proto "https"

    ProxyPass        /api/ http://127.0.0.1:8300/api/
    ProxyPassReverse /api/ http://127.0.0.1:8300/api/
    ProxyPass        /health http://127.0.0.1:8300/health
    ProxyPassReverse /health http://127.0.0.1:8300/health
    ProxyPass        / http://127.0.0.1:3300/
    ProxyPassReverse / http://127.0.0.1:3300/

    ErrorLog ${APACHE_LOG_DIR}/sportsintel-error.log
    CustomLog ${APACHE_LOG_DIR}/sportsintel-access.log combined
</VirtualHost>
```

Obtain and renew certificates with the organization’s ACME/Certbot process.
Verify automatic renewal before launch. HSTS is emitted by the API only when
`SPORTSINTEL_ENV=production`; do not enable production mode before HTTPS works.

## Firewall

Permit SSH only from approved administration networks and expose only TCP 80 and
443 publicly. Deny public access to 3000, 8000, 3300, 8300, and 5432. Production
Compose does not publish PostgreSQL. Its application ports bind to `127.0.0.1`, providing
an additional boundary but not replacing host firewall policy.

## Administrative API

Destructive snapshot-history routes require `X-Admin-Key`:

```bash
curl -X POST -H "X-Admin-Key: $SPORTSINTEL_ADMIN_KEY" \
  https://sports.example.com/api/sports/nfl/history/clear
```

Missing or incorrect keys return HTTP 401. Never place the key in a URL, shell
history, Apache access log format, or support transcript. Protect future
administrative endpoints with the same FastAPI dependency.

Rate limiting is intentionally lightweight and process-local. The supported
first deployment runs one API worker. Before adding API replicas or workers,
move enforcement to the trusted reverse proxy or a shared rate-limit service so
all processes apply one limit budget.

## Backup and restore

Back up PostgreSQL before every deployment and on a scheduled retention policy:

```bash
docker compose exec -T postgres sh -c \
  'pg_dump --username="$POSTGRES_USER" --format=custom "$POSTGRES_DB"' \
  > /secure/backups/sportsintel-$(date -u +%Y%m%dT%H%M%SZ).dump
```

Copy the `data/` directory according to the same encrypted backup policy. Test
restores regularly on an isolated host. To restore PostgreSQL, stop API/web,
create or clean the target database, and run:

```bash
docker compose stop api web
docker compose exec -T postgres sh -c \
  'pg_restore --username="$POSTGRES_USER" --dbname="$POSTGRES_DB" --clean --if-exists' \
  < /secure/backups/approved.dump
docker compose up -d
```

The snapshot schema initialization file is idempotent, but restoring the database
is preferred when historical snapshots must be retained.

## Health monitoring and logs

Monitor both endpoints through HTTPS:

- `/health` — application, PostgreSQL, snapshot store, version, build timestamp,
  commit, and environment.
- `/api/sports/nfl/snapshot-store/health` — detailed persistence reachability.

Alert on non-200 responses, `status: degraded`, PostgreSQL/table reachability
failures, container unhealthy state, restart loops, and disk/volume capacity.
Application logs are JSON request records on container stdout/stderr and contain
request ID, path, status, latency, and client IP. They intentionally omit query
strings and request headers. Read them with `docker compose logs api`; Apache
access/error logs are under `/var/log/apache2/` using the paths above. Forward
both streams to the production log platform with retention and access controls.

## Rollback

Record the previously deployed Git commit and database backup before rollout.
For an application-only rollback:

```bash
git checkout <previous-reviewed-commit-or-tag>
docker compose build api web
docker compose up -d
```

Verify both health endpoints and critical read-only pages. This sprint does not
change the snapshot schema. If a later release includes a data migration, follow
that migration’s explicit backward-compatibility and restore instructions rather
than rolling database state back blindly.
