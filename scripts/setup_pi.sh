#!/usr/bin/env bash
# Automated setup for Film Scanner on a fresh Raspberry Pi
# Copies the app to /opt/film-scanner, creates a venv, installs deps,
# registers a systemd service, and adds helper commands.

set -euo pipefail

if [[ ${EUID:-$(id -u)} -ne 0 ]]; then
  echo "Please run with sudo:"
  echo "  sudo bash $0"
  exit 1
fi

APP_USER=${SUDO_USER:-pi}
# Fall back gracefully if expected user doesn't exist (e.g., custom Pi images)
if ! id -u "$APP_USER" >/dev/null 2>&1; then
  APP_USER="$(logname 2>/dev/null || echo root)"
fi
APP_DIR="/opt/film-scanner"
SERVICE_NAME="film-scanner.service"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

echo "========================================="
echo " Film Scanner - Raspberry Pi Installer"
echo "========================================="
echo "User:      $APP_USER"
echo "Source:    $REPO_ROOT"
echo "Install:   $APP_DIR"
echo "Service:   $SERVICE_NAME"
echo "========================================="

# Basic Pi detection (non-fatal)
if [[ -f /proc/device-tree/model ]] && grep -qi "raspberry pi" /proc/device-tree/model; then
  echo "Detected Raspberry Pi hardware."
else
  echo "Warning: Raspberry Pi not detected. Continuing anyway..."
fi

echo ""
echo "Installing system packages..."
export DEBIAN_FRONTEND=noninteractive
apt-get update -y
apt-get install -y \
  python3 python3-pip python3-venv git gphoto2 rsync \
  libatlas-base-dev libjpeg-dev libtiff5 libopenjp2-7 \
  avahi-daemon

echo ""
echo "Copying application to $APP_DIR ..."
mkdir -p "$APP_DIR"
rsync -a --delete \
  --exclude ".git" \
  --exclude ".github" \
  "$REPO_ROOT"/ "$APP_DIR"/

echo ""
echo "Creating virtual environment..."
if [[ ! -f "$APP_DIR/.venv/bin/python" ]]; then
  python3 -m venv "$APP_DIR/.venv"
fi
"$APP_DIR/.venv/bin/pip" install --upgrade pip
"$APP_DIR/.venv/bin/pip" install -r "$APP_DIR/requirements.txt"

echo ""
echo "Preparing data directories..."
install -d -o "$APP_USER" -g "$APP_USER" "/home/$APP_USER/scans"
install -d -o "$APP_USER" -g "$APP_USER" "/home/$APP_USER/.film_scanner"

echo ""
echo "Seeding default configuration (non-interactive)..."
(
  cd "$APP_DIR"
  sudo -u "$APP_USER" env HOME="/home/$APP_USER" PYTHONPATH="$APP_DIR" \
    "$APP_DIR/.venv/bin/python" - <<'PY'
from config_manager import ConfigManager
from datetime import datetime
import socket

cfg = ConfigManager()
if cfg.config_exists():
    print(f"Config already present at {cfg.config_file}")
else:
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
    except Exception:
        ip = "127.0.0.1"
    data = {
        "setup_complete": True,
        "setup_date": datetime.now().isoformat(),
        "mode": "local",
        "pi_ip": ip,
        "hostname": socket.gethostname(),
        "port": 5000,
        "camera_type": "gphoto2",
        "canon_wifi_enabled": False
    }
    if cfg.save_config(data):
        print(f"Config created at {cfg.config_file}")
    else:
        print("Failed to create config")
PY
)

echo ""
echo "Writing systemd service..."
cat >/etc/systemd/system/$SERVICE_NAME <<EOF
[Unit]
Description=Film Scanner Web App
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=$APP_USER
WorkingDirectory=$APP_DIR
Environment=PYTHONUNBUFFERED=1
ExecStart=$APP_DIR/.venv/bin/python $APP_DIR/web_app.py
Restart=on-failure
RestartSec=3

[Install]
WantedBy=multi-user.target
EOF

echo ""
echo "Reloading systemd and enabling service..."
systemctl daemon-reload
systemctl enable "$SERVICE_NAME"
systemctl restart "$SERVICE_NAME"

echo ""
echo "Installing helper commands (start-scanner, stop-scanner)..."
cat >/usr/local/bin/start-scanner <<'EOF'
#!/usr/bin/env bash
if [[ ${EUID:-$(id -u)} -ne 0 ]]; then
  exec sudo "$0" "$@"
fi
systemctl start film-scanner.service
systemctl status film-scanner.service --no-pager --lines=20
EOF
chmod +x /usr/local/bin/start-scanner

cat >/usr/local/bin/stop-scanner <<'EOF'
#!/usr/bin/env bash
if [[ ${EUID:-$(id -u)} -ne 0 ]]; then
  exec sudo "$0" "$@"
fi
systemctl stop film-scanner.service
systemctl status film-scanner.service --no-pager --lines=20
EOF
chmod +x /usr/local/bin/stop-scanner

echo ""
echo "========================================="
echo "Install complete."
echo "- Service: $SERVICE_NAME (enabled + started)"
echo "- Start manually: start-scanner"
echo "- Stop manually:  stop-scanner"
echo "- Logs:           journalctl -u $SERVICE_NAME -f"
echo "========================================="

