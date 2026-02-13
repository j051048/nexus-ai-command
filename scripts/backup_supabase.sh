#!/usr/bin/env bash
# Nexus AI Command — Supabase Database Backup Script
# Usage: ./scripts/backup_supabase.sh
# Requires: pg_dump, gzip, and DATABASE_URL environment variable
#
# Schedule via cron:
#   0 */6 * * * /path/to/scripts/backup_supabase.sh >> /var/log/nexus_backup.log 2>&1

set -euo pipefail

# Configuration
BACKUP_DIR="${BACKUP_DIR:-./backups}"
RETENTION_DAYS="${RETENTION_DAYS:-30}"
DATABASE_URL="${DATABASE_URL:?ERROR: DATABASE_URL environment variable is required}"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
BACKUP_FILE="${BACKUP_DIR}/nexus_backup_${TIMESTAMP}.sql.gz"

echo "[$(date -Iseconds)] Starting Supabase backup..."

# Ensure backup directory exists
mkdir -p "${BACKUP_DIR}"

# Run pg_dump with compression
pg_dump "${DATABASE_URL}" \
  --no-owner \
  --no-privileges \
  --clean \
  --if-exists \
  --format=plain \
  | gzip > "${BACKUP_FILE}"

FILESIZE=$(du -sh "${BACKUP_FILE}" | cut -f1)
echo "[$(date -Iseconds)] Backup completed: ${BACKUP_FILE} (${FILESIZE})"

# Clean up old backups
if [ "${RETENTION_DAYS}" -gt 0 ]; then
  DELETED=$(find "${BACKUP_DIR}" -name "nexus_backup_*.sql.gz" -mtime +"${RETENTION_DAYS}" -delete -print | wc -l)
  if [ "${DELETED}" -gt 0 ]; then
    echo "[$(date -Iseconds)] Cleaned up ${DELETED} backups older than ${RETENTION_DAYS} days"
  fi
fi

echo "[$(date -Iseconds)] Backup process complete."
