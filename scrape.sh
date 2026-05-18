#!/usr/bin/env bash
# Scrape Apifox doc site + regenerate openapi + commit any diff.
# Crontab-friendly: cd to script dir, run quietly, commit only on change.
set -euo pipefail

DOMAIN="${APIFOX_DOMAIN:-openapi.qixiangyun.com}"
PROJECT_ID="${APIFOX_PROJECT_ID:-2393904}"
REPO_DIR="$(cd "$(dirname "$0")" && pwd)"
DUMP_DIR="$REPO_DIR/apifox-dump/$PROJECT_ID"
LOG_FILE="$REPO_DIR/scrape.log"

cd "$REPO_DIR"

{
  echo "===== $(date -Is)  scrape start  domain=$DOMAIN ====="
  python3 apifox_scrape.py "$DOMAIN"
  python3 apifox_to_openapi.py "$DUMP_DIR" --out "$DUMP_DIR/openapi.yaml" --title "七翔云开放平台"
  python3 apifox_split_openapi.py "$DUMP_DIR"
  echo "===== $(date -Is)  scrape done ====="
} >> "$LOG_FILE" 2>&1

# Commit any changes (no-op if dump unchanged).
if [ -n "$(git status --porcelain)" ]; then
  git add -A
  git -c user.name="apifox-watch" -c user.email="apifox-watch@localhost" \
      commit -m "scrape: $(date -Is)" >> "$LOG_FILE" 2>&1
  echo "$(date -Is)  committed changes" >> "$LOG_FILE"
else
  echo "$(date -Is)  no changes" >> "$LOG_FILE"
fi
