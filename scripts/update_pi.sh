#!/usr/bin/env bash
# ============================================================================
# Film Scanner - Update Pi install from a git clone
# ============================================================================
# Run this FROM A GIT CLONE (e.g. ~/Film-Scanner), not from /opt/film-scanner.
# /opt/film-scanner is a copy; it has no .git so you cannot "git pull" there.
#
# First-time: clone somewhere, then run setup_pi.sh once:
#   cd ~ && git clone https://github.com/ccyyturralde/Film-Scanner.git
#   cd Film-Scanner && sudo bash scripts/setup_pi.sh
#
# Later updates: from that same clone, pull and sync to /opt:
#   cd ~/Film-Scanner && sudo bash scripts/update_pi.sh
# ============================================================================

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
APP_DIR="/opt/film-scanner"

if [[ ! -d "$REPO_ROOT/.git" ]]; then
    echo "ERROR: Not a git repository: $REPO_ROOT"
    echo "Run this script from a git clone (e.g. ~/Film-Scanner), not from /opt/film-scanner."
    echo ""
    echo "If you don't have a clone yet:"
    echo "  cd ~ && git clone https://github.com/ccyyturralde/Film-Scanner.git"
    echo "  cd Film-Scanner && sudo bash scripts/setup_pi.sh"
    exit 1
fi

if [[ ${EUID:-$(id -u)} -ne 0 ]]; then
    echo "Run with sudo: sudo bash scripts/update_pi.sh"
    exit 1
fi

echo "Updating from $REPO_ROOT to $APP_DIR ..."
cd "$REPO_ROOT"
git pull

echo "Syncing files to $APP_DIR ..."
mkdir -p "$APP_DIR"
rsync -a --delete \
    --exclude ".git" \
    --exclude ".github" \
    --exclude "__pycache__" \
    --exclude "*.pyc" \
    --exclude ".venv" \
    "$REPO_ROOT"/ "$APP_DIR"/

# Restart whichever service is active.
# The touchscreen service manages web_app.py internally, so if it's running
# we restart that (which will re-launch web_app.py). Otherwise restart the
# standalone web service.
if systemctl is-active --quiet film-scanner-touchscreen.service; then
    echo "Restarting film-scanner-touchscreen.service (manages web app) ..."
    systemctl restart film-scanner-touchscreen.service
    echo "Done. Check: systemctl status film-scanner-touchscreen.service"
elif systemctl is-enabled --quiet film-scanner.service 2>/dev/null; then
    echo "Restarting film-scanner.service ..."
    systemctl restart film-scanner.service
    echo "Done. Check: systemctl status film-scanner.service"
else
    echo "No active scanner service found. Start manually if needed:"
    echo "  sudo systemctl start film-scanner-touchscreen.service"
    echo "  # or: sudo systemctl start film-scanner.service"
fi
