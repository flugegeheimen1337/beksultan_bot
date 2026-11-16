#!/bin/bash
set -euo pipefail

APP_DIR=/opt/finance-bot

if [[ ! -f "$APP_DIR/.env" ]]; then
  echo ".env is missing in $APP_DIR" >&2
  exit 1
fi

if ! id financebot >/dev/null 2>&1; then
  useradd --system --home "$APP_DIR" --shell /usr/sbin/nologin financebot
fi

export DEBIAN_FRONTEND=noninteractive
apt-get update
apt-get install -y python3 python3-venv python3-pip

python3 -m venv "$APP_DIR/venv"
"$APP_DIR/venv/bin/pip" install --upgrade pip
"$APP_DIR/venv/bin/pip" install -r "$APP_DIR/requirements.txt"

mkdir -p "$APP_DIR/data"
chown -R financebot:financebot "$APP_DIR"
chmod 600 "$APP_DIR/.env"

cp "$APP_DIR/deploy/finance-bot.service" /etc/systemd/system/finance-bot.service
systemctl daemon-reload
systemctl enable finance-bot
systemctl restart finance-bot

for _ in 1 2 3 4 5 6 7 8 9 10 11 12 13 14 15; do
  if systemctl is-active --quiet finance-bot; then
    systemctl --no-pager --full status finance-bot
    exit 0
  fi
  sleep 1
done

systemctl --no-pager --full status finance-bot || true
journalctl -u finance-bot -n 80 --no-pager
exit 1
