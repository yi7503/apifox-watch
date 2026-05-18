#!/usr/bin/env bash
# Scrape Apifox doc site + regenerate openapi.
# On any change: push to a scrape/<date> branch and open a PR against main.
# Crontab-friendly: cd to script dir, run quietly.
set -euo pipefail

DOMAIN="${APIFOX_DOMAIN:-openapi.qixiangyun.com}"
PROJECT_ID="${APIFOX_PROJECT_ID:-2393904}"
REPO_DIR="$(cd "$(dirname "$0")" && pwd)"
DUMP_DIR="$REPO_DIR/apifox-dump/$PROJECT_ID"
LOG_FILE="$REPO_DIR/scrape.log"
STAMP="$(date +%Y-%m-%d)"
BRANCH="scrape/$STAMP"

cd "$REPO_DIR"
git fetch origin main --quiet
git checkout main --quiet
git reset --hard origin/main --quiet

{
  echo "===== $(date -Is)  scrape start  domain=$DOMAIN  branch=$BRANCH ====="
  python3 apifox_scrape.py "$DOMAIN"
  # Pin the title — must match what's already committed in the dump so scrape
  # diffs don't show 14 title-only changes every run. Default is
  # "Apifox project <id>", which is not what's on disk.
  python3 apifox_to_openapi.py "$DUMP_DIR" --out "$DUMP_DIR/openapi.yaml" --title "七翔云开放平台"
  python3 apifox_split_openapi.py "$DUMP_DIR"
  echo "===== $(date -Is)  scrape done ====="
} >> "$LOG_FILE" 2>&1

if [ -z "$(git status --porcelain)" ]; then
  echo "$(date -Is)  no changes" >> "$LOG_FILE"
  exit 0
fi

# Create / reset the scrape branch and commit there.
git checkout -B "$BRANCH" --quiet
git add -A
git -c user.name="apifox-watch" -c user.email="apifox-watch@localhost" \
    commit -m "scrape: $(date -Is)" >> "$LOG_FILE" 2>&1
echo "$(date -Is)  committed changes on $BRANCH" >> "$LOG_FILE"

git push --force-with-lease origin "$BRANCH" >> "$LOG_FILE" 2>&1 && \
  echo "$(date -Is)  pushed $BRANCH" >> "$LOG_FILE" || {
    echo "$(date -Is)  push failed" >> "$LOG_FILE"; exit 1; }

# Open PR (or reuse existing open PR on this branch).
if gh pr view "$BRANCH" --json number >/dev/null 2>&1; then
  echo "$(date -Is)  PR already open for $BRANCH" >> "$LOG_FILE"
else
  gh pr create --base main --head "$BRANCH" \
    --title "scrape: $STAMP" \
    --body "Automated Apifox scrape on $STAMP. Review the dump diff before merging." \
    >> "$LOG_FILE" 2>&1 && \
    echo "$(date -Is)  opened PR for $BRANCH" >> "$LOG_FILE"
fi
