# Deploy on a Linux server

[← Back to the README](../README.md)

1. [Prepare the server](#1-prepare-the-server)
2. [Get the files and create `.env`](#2-get-the-files-and-create-env)
3. [Log in to the registry (only if the package is private)](#3-log-in-to-the-registry-only-if-the-package-is-private)
4. [Start it](#4-start-it)
5. [Update to a new version](#5-update-to-a-new-version)
6. [Roll back](#6-roll-back)
7. [Back up the database](#7-back-up-the-database)
8. [Restore](#8-restore)
9. [HTTPS](#9-https)
10. [Where the secrets live](#where-the-secrets-live)

This runs the **published image** on a server you control. CI builds it on every push to
`main` and publishes it to GitHub Container Registry as `ghcr.io/nredka/social-network`
(for `linux/amd64` and `linux/arm64`), tagged `sha-<short commit>` and `latest`. The
server needs only two files, `compose.prod.yml` and `.env`: no source code, no build
tools. The steps below were rehearsed on a throwaway stack (start, migrate, update, roll
back, back up, wipe and restore).

How it differs from the development setup (`docker-compose.yml`): it pulls the image
instead of building it; PostgreSQL is **not published** to the host (only the API can
reach it); the API listens on `127.0.0.1` for a reverse proxy; container logs are rotated;
and the API container is read-only, has no Linux capabilities and cannot gain privileges.

## 1. Prepare the server

You need a Linux server (these commands are for Ubuntu LTS), SSH access and, for HTTPS, a
domain name pointing at it.

**Install Docker Engine and the Compose plugin** from Docker's official repository, not
from Ubuntu's `docker.io` package (older, and it conflicts with the official one):

```bash
sudo apt update
sudo apt install ca-certificates curl
sudo install -m 0755 -d /etc/apt/keyrings
sudo curl -fsSL https://download.docker.com/linux/ubuntu/gpg -o /etc/apt/keyrings/docker.asc
sudo chmod a+r /etc/apt/keyrings/docker.asc

sudo tee /etc/apt/sources.list.d/docker.sources <<EOF
Types: deb
URIs: https://download.docker.com/linux/ubuntu
Suites: $(. /etc/os-release && echo "${UBUNTU_CODENAME:-$VERSION_CODENAME}")
Components: stable
Architectures: $(dpkg --print-architecture)
Signed-By: /etc/apt/keyrings/docker.asc
EOF

sudo apt update
sudo apt install docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
docker compose version
```

**Create a non-root deploy user** and work as that user, not as root:

```bash
sudo adduser deploy
sudo usermod -aG docker deploy      # lets "deploy" run docker without sudo
```

> Membership in the `docker` group is **equivalent to root**: anyone who can start a
> container can mount the host's file system into it. Put only people you would trust
> with root in that group, and protect that account (SSH keys, no password login).

**Firewall:** allow only SSH, HTTP and HTTPS.

```bash
sudo ufw default deny incoming
sudo ufw allow 22/tcp
sudo ufw allow 80/tcp
sudo ufw allow 443/tcp
sudo ufw enable
```

> A port that a container **publishes on all interfaces bypasses `ufw`**: Docker adds its
> own firewall rules ahead of it. That is why `compose.prod.yml` publishes the API only
> on `127.0.0.1` and does not publish the database at all. Do not "fix" it by changing
> those bindings.

## 2. Get the files and create `.env`

As the `deploy` user, on the server:

```bash
mkdir -p ~/social-network && cd ~/social-network
curl -fsSLO https://raw.githubusercontent.com/nredka/social-network/main/compose.prod.yml
curl -fsSL https://raw.githubusercontent.com/nredka/social-network/main/.env.example -o .env
```

(If the repository is private, copy the two files from your computer with `scp` instead.)

Generate strong secrets and set the production values. This keeps only what the server
needs: the two database URL lines are for development, and Compose builds the real one
from the `POSTGRES_*` values.

```bash
JWT=$(openssl rand -hex 32)
PW=$(openssl rand -hex 24)
sed -i.bak \
  -e "s|^JWT_SECRET_KEY=.*|JWT_SECRET_KEY=$JWT|" \
  -e "s|^POSTGRES_PASSWORD=.*|POSTGRES_PASSWORD=$PW|" \
  -e "s|^ENVIRONMENT=.*|ENVIRONMENT=production|" \
  -e '/^DATABASE_URL=/d' -e '/^TEST_DATABASE_URL=/d' .env && rm .env.bak
chmod 600 .env          # only your user can read it
```

Then add the image tag to run. **Pin an immutable `sha-...` tag**, copied from the
repository's Packages page or from the "Docker" workflow run:

```bash
echo 'IMAGE_TAG=sha-1a2b3c4' >> .env
```

(`latest` also works, but it moves with every release, so you cannot tell what is
running or go back to it.) `API_PORT` defaults to `8000`.

## 3. Log in to the registry (only if the package is private)

A package is pulled without logging in once its visibility is **public**. If it is
private, create a **personal access token (classic)** on GitHub with only the
`read:packages` scope (GitHub Packages does not accept fine-grained tokens), then:

```bash
echo YOUR_TOKEN | docker login ghcr.io -u YOUR_GITHUB_USERNAME --password-stdin
```

## 4. Start it

```bash
docker compose -f compose.prod.yml pull
docker compose -f compose.prod.yml up -d
docker compose -f compose.prod.yml run --rm api alembic upgrade head   # create the tables
curl http://127.0.0.1:8000/health                                       # {"status":"ok"}
docker compose -f compose.prod.yml ps                                   # both "healthy"
docker compose -f compose.prod.yml logs -f api                          # Ctrl+C to stop following
```

The migrations are a separate step on purpose (several replicas would race, and a failing
migration would put the container in a restart loop). Run them after the first start and
after every update that adds a migration. To avoid typing `-f compose.prod.yml` every
time: `export COMPOSE_FILE=compose.prod.yml`.

## 5. Update to a new version

Take a backup first (step 7), then:

```bash
# 1. put the new tag into .env, e.g. IMAGE_TAG=sha-9f8e7d6
nano .env
# 2. download it, apply its migrations (this runs the NEW image), switch over
docker compose -f compose.prod.yml pull
docker compose -f compose.prod.yml run --rm api alembic upgrade head
docker compose -f compose.prod.yml up -d
docker compose -f compose.prod.yml ps
```

`up -d` recreates only the `api` container; the database keeps running. Write migrations
so the **previous** version of the code still works with the new schema (add columns and
tables first, remove or rename in a later release): while you update, and if you have to
roll back, old code runs against the new schema.

## 6. Roll back

Put the previous tag back into `.env` and run `docker compose -f compose.prod.yml up -d`.
This is why production pins `sha-...` tags: the old image is still in the registry.

A release that **changed the database** is harder. If the migration only added things, the
old code usually runs fine against the new schema and you can stop here. If it removed or
renamed something, the old code breaks and the migration must be undone first, **with the
new image** (the old one does not contain the newer migration, and Alembic answers "Can't
locate revision"):

```bash
docker compose -f compose.prod.yml run --rm api alembic downgrade -1
# then put the previous IMAGE_TAG back and run: up -d
```

That is risky: a downgrade can drop a column or a table and **the data written to it since
the update is lost**. So: back up before every update, prefer fixing forward with a new
release, and keep migrations backward compatible so a rollback does not need a downgrade.

## 7. Back up the database

A backup in PostgreSQL's custom format (compressed, and `pg_restore` can restore parts
of it). `-T` is required: without it Docker adds a terminal that corrupts the binary
output.

```bash
mkdir -p backups && chmod 700 backups
docker compose -f compose.prod.yml exec -T db sh -c \
  'pg_dump -U "$POSTGRES_USER" -d "$POSTGRES_DB" -Fc' \
  > "backups/social-network-$(date +%Y%m%d-%H%M%S).dump"
```

For regular backups use a script that never leaves a half-written file behind. Save it as
`~/social-network/backup.sh` and run `chmod +x backup.sh`:

```bash
#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"
mkdir -p backups
out="backups/social-network-$(date +%Y%m%d-%H%M%S).dump"
trap 'rm -f "$out.partial"' EXIT           # no half-written file, whatever happens
docker compose -f compose.prod.yml exec -T db sh -c 'pg_dump -U "$POSTGRES_USER" -d "$POSTGRES_DB" -Fc' > "$out.partial"
mv "$out.partial" "$out"
chmod 600 "$out"
find backups -name '*.dump' -mtime +14 -delete    # keep 14 days on the server
echo "backup written: $out"
```

A failed backup exits with a non-zero status and leaves nothing behind. Run it every night
with cron (`crontab -e`):

```
0 3 * * * /home/deploy/social-network/backup.sh >> /home/deploy/backup.log 2>&1
```

**A backup on the same machine is not a backup**: if the disk or the server is lost, both
go. Copy the dump files to another place (another server with `rsync`/`scp`, or object
storage with a tool like `rclone`), and treat them like secrets: they contain every
user's data and password hash.

## 8. Restore

Stop the API first: PostgreSQL refuses to drop a database that is in use ("is being
accessed by other users").

```bash
docker compose -f compose.prod.yml stop api
docker compose -f compose.prod.yml exec -T db sh -c \
  'psql -U "$POSTGRES_USER" -d postgres -c "DROP DATABASE \"$POSTGRES_DB\"" -c "CREATE DATABASE \"$POSTGRES_DB\""'
docker compose -f compose.prod.yml exec -T db sh -c \
  'pg_restore -U "$POSTGRES_USER" -d "$POSTGRES_DB" --no-owner' < backups/social-network-YYYYMMDD-HHMMSS.dump
docker compose -f compose.prod.yml up -d api
```

The dump includes the `alembic_version` table, so the restored database knows which
migrations it has. Passwords keep working (hashes are restored), and tokens issued before
stay valid as long as `JWT_SECRET_KEY` has not changed.

**Test your restores.** A backup you have never restored is a hope, not a backup. Every
so often restore the newest dump into a throwaway copy of the stack (for example with
`docker compose -p restore-test -f compose.prod.yml ...` in a separate directory with its
own `.env`), check the data, and then remove it.

## 9. HTTPS

The API speaks plain HTTP on `127.0.0.1:8000`. In front of it put a **reverse proxy** on
the same server that terminates HTTPS and forwards to that port. This is not implemented
in this repository. The simplest choice is [Caddy](https://caddyserver.com/), which gets
and renews a Let's Encrypt certificate by itself once your domain points at the server
and ports 80 and 443 are open; a `Caddyfile` is all it needs:

```
api.example.com {
    reverse_proxy 127.0.0.1:8000
}
```

nginx with Certbot does the same with more configuration. Never publish the API port
itself to the internet: tokens and passwords would travel unencrypted.

## Where the secrets live

| Secret | Where it lives | Notes |
| ------ | -------------- | ----- |
| `JWT_SECRET_KEY`, `POSTGRES_PASSWORD` (production) | `.env` **on the server**, mode `600`, never in Git | Compose passes them to the container's environment when it starts. |
| `GITHUB_TOKEN` | created by GitHub for each workflow run, gone when it ends | Its rights are the `permissions:` of the workflow; used to push the image. Nothing to store. |
| GitHub Secrets | for CI, if it ever needs a real secret | Encrypted, hidden in logs, not given to pull requests from forks. Today CI needs none: its JWT key is a throwaway value that protects nothing. |
| Personal access token (`read:packages`) | on the server, kept by `docker login` (by default in `~/.docker/config.json`), only if the package is private | Read-only, classic token. Not needed for a public package. |

**Secrets are never baked into the image.** Anything copied or set while building ends
up in a layer, and `docker history` shows every layer, so whoever has the image has the
secret, and deleting it in a later step does not remove it from the earlier layer.
`.dockerignore` keeps `.env` out of the build, the `Dockerfile` has no secret `ENV`, and
the image was checked: no `.env` file, no secret value in any file, nothing in
`docker history`. The values reach the **running** container from `.env`, so anyone who
can run `docker inspect` on the server can read them: another reason the `docker` group
is root-equivalent. For stricter setups use a secrets manager or Docker secrets.

**Rotating `JWT_SECRET_KEY`** invalidates **every** access token: all users get a `401`
and must log in again (tested). Change the value in `.env` and run
`docker compose -f compose.prod.yml up -d` (the key is read at startup, so the container
is recreated). Passwords and data do not depend on this key. Rotate it at once if it may
have leaked.

**Changing `POSTGRES_PASSWORD` in `.env` does not change the password of an existing
database.** PostgreSQL reads that variable only when it first creates the data directory.
To rotate it, also run `ALTER USER ... PASSWORD '...'` inside the database, then update
`.env`.
