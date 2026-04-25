#!/usr/bin/env bash
set -euo pipefail

# Push inicial al repo público (ajusta si ya tienes commits).
REPO_URL="${REPO_URL:-https://github.com/genaudius/Genaudius-mcp.git}"

if [[ ! -d .git ]]; then
  git init
  git add .
  git commit -m "Initial commit: GeanAudius MCP v2" || true
  git branch -M main
  git remote add origin "$REPO_URL"
  echo "Created git repo. Run: git push -u origin main"
else
  echo "Already a git repo. Set remote if needed:"
  echo "  git remote add origin $REPO_URL   # if missing"
  echo "  git push -u origin main"
fi
