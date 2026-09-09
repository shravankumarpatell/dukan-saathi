#!/usr/bin/env bash
# Self-healing PostgreSQL 18 bootstrap for the dev container.
# - Binaries live in /usr/lib/postgresql/18 (apt) with a persistent backup in /root/pg18
# - Data directory lives in /app/data/pg (persistent)
# - Called from backend startup (server.py) and can be run manually.
set -euo pipefail

PG_MAJOR=18
PG_SYS_DIR="/usr/lib/postgresql/${PG_MAJOR}"
PG_BACKUP_DIR="/root/pg${PG_MAJOR}"
PG_DATA="/app/data/pg"
PG_PORT="${PG_PORT:-5432}"
PG_LOG="/app/data/pg.log"
DB_USER="${PG_APP_USER:-tileos}"
DB_PASS="${PG_APP_PASSWORD:-tileos}"
DB_NAME="${PG_APP_DB:-tileos}"

log() { echo "[ensure_pg] $*"; }

# 1. Make sure binaries exist (restore from backup or re-install via apt)
if [ ! -x "${PG_SYS_DIR}/bin/postgres" ]; then
  if [ -x "${PG_BACKUP_DIR}/bin/postgres" ]; then
    log "restoring PostgreSQL binaries from ${PG_BACKUP_DIR}"
    mkdir -p "${PG_SYS_DIR}"
    cp -a "${PG_BACKUP_DIR}/." "${PG_SYS_DIR}/"
    # shared libs shipped with libpq5 / postgres server
    if [ -d "${PG_BACKUP_DIR}/_libs" ]; then
      cp -a "${PG_BACKUP_DIR}/_libs/." /usr/lib/aarch64-linux-gnu/ 2>/dev/null || cp -a "${PG_BACKUP_DIR}/_libs/." /usr/lib/x86_64-linux-gnu/ 2>/dev/null || true
    fi
    if [ -d "${PG_BACKUP_DIR}/_share" ]; then
      mkdir -p /usr/share/postgresql/${PG_MAJOR}
      cp -a "${PG_BACKUP_DIR}/_share/." /usr/share/postgresql/${PG_MAJOR}/
    fi
  else
    log "installing PostgreSQL ${PG_MAJOR} via apt (this takes ~1 min)"
    export DEBIAN_FRONTEND=noninteractive
    apt-get install -y -qq curl ca-certificates gnupg lsb-release >/dev/null 2>&1 || true
    install -d /usr/share/postgresql-common/pgdg
    curl -fsSL -o /usr/share/postgresql-common/pgdg/apt.postgresql.org.asc https://www.postgresql.org/media/keys/ACCC4CF8.asc
    echo "deb [signed-by=/usr/share/postgresql-common/pgdg/apt.postgresql.org.asc] https://apt.postgresql.org/pub/repos/apt $(lsb_release -cs)-pgdg main" > /etc/apt/sources.list.d/pgdg.list
    apt-get update -qq
    apt-get install -y -qq postgresql-${PG_MAJOR}
  fi
fi

# 2. Keep a persistent backup of binaries + share files + libpq
if [ ! -x "${PG_BACKUP_DIR}/bin/postgres" ]; then
  log "backing up PostgreSQL binaries to ${PG_BACKUP_DIR}"
  mkdir -p "${PG_BACKUP_DIR}/_libs" "${PG_BACKUP_DIR}/_share"
  cp -a "${PG_SYS_DIR}/." "${PG_BACKUP_DIR}/"
  cp -a /usr/share/postgresql/${PG_MAJOR}/. "${PG_BACKUP_DIR}/_share/" 2>/dev/null || true
  for lib in $(ldd "${PG_SYS_DIR}/bin/postgres" "${PG_SYS_DIR}/bin/psql" | awk '/=> \//{print $3}' | sort -u); do
    case "$lib" in
      *libpq*|*libllvm*|*libicu*|*liburing*|*libxml2*|*libxslt*|*liblz4*|*libzstd*|*libgssapi*|*libldap*|*liblber*|*libsasl*|*libkrb5*|*libk5crypto*|*libkeyutils*|*libedit*|*libbsd*|*libmd*) cp -aL "$lib" "${PG_BACKUP_DIR}/_libs/" 2>/dev/null || true ;;
    esac
  done
fi

# 3. Ensure postgres OS user exists
if ! id postgres >/dev/null 2>&1; then
  log "creating postgres system user"
  useradd -r -M -s /bin/bash postgres
fi

# 4. Init data dir if needed
mkdir -p /app/data
if [ ! -f "${PG_DATA}/PG_VERSION" ]; then
  log "initializing data directory at ${PG_DATA}"
  mkdir -p "${PG_DATA}"
  chown -R postgres:postgres "${PG_DATA}"
  chmod 700 "${PG_DATA}"
  su postgres -c "${PG_SYS_DIR}/bin/initdb -D ${PG_DATA} -U postgres --auth-local=trust --auth-host=scram-sha-256 -E UTF8 --locale=C.UTF-8" >/dev/null
  cat >> "${PG_DATA}/postgresql.conf" <<EOF
listen_addresses = '127.0.0.1'
port = ${PG_PORT}
max_connections = 100
shared_buffers = 256MB
logging_collector = off
EOF
  echo "host all all 127.0.0.1/32 scram-sha-256" >> "${PG_DATA}/pg_hba.conf"
else
  chown -R postgres:postgres "${PG_DATA}"
  chmod 700 "${PG_DATA}"
fi
touch "${PG_LOG}"; chown postgres:postgres "${PG_LOG}"
mkdir -p /var/run/postgresql && chown postgres:postgres /var/run/postgresql

# 5. Start server if not running
if ! su postgres -c "${PG_SYS_DIR}/bin/pg_isready -q -h /var/run/postgresql -p ${PG_PORT}"; then
  log "starting PostgreSQL on port ${PG_PORT}"
  # remove stale pid if any
  if [ -f "${PG_DATA}/postmaster.pid" ]; then
    PID=$(head -1 "${PG_DATA}/postmaster.pid")
    if ! kill -0 "$PID" 2>/dev/null; then rm -f "${PG_DATA}/postmaster.pid"; fi
  fi
  su postgres -c "${PG_SYS_DIR}/bin/pg_ctl -D ${PG_DATA} -l ${PG_LOG} -w -t 60 start" >/dev/null
fi

# 6. Ensure app role + database
PSQL="${PG_SYS_DIR}/bin/psql -v ON_ERROR_STOP=1 -h /var/run/postgresql -p ${PG_PORT} -U postgres"
su postgres -c "$PSQL -tAc \"SELECT 1 FROM pg_roles WHERE rolname='${DB_USER}'\"" | grep -q 1 || \
  su postgres -c "$PSQL -c \"CREATE ROLE ${DB_USER} LOGIN PASSWORD '${DB_PASS}' SUPERUSER\""
su postgres -c "$PSQL -tAc \"SELECT 1 FROM pg_database WHERE datname='${DB_NAME}'\"" | grep -q 1 || \
  su postgres -c "$PSQL -c \"CREATE DATABASE ${DB_NAME} OWNER ${DB_USER}\""

log "PostgreSQL ready: postgresql://${DB_USER}@127.0.0.1:${PG_PORT}/${DB_NAME}"
