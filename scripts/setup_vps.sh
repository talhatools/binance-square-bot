#!/usr/bin/env bash
# ==============================================================================
# Automated Binance Square Posting Bot - Turnkey Ubuntu VPS Setup Script
# ==============================================================================
set -e

echo "========================================================"
echo " Starting Automated Binance Square Bot Setup on Ubuntu"
echo "========================================================"

# 1. Update OS packages and install Python 3.11+, pip, venv, and build tools
echo "[1/5] Updating packages and installing prerequisites..."
sudo apt update && sudo apt upgrade -y
sudo apt install -y python3 python3-pip python3-venv git curl

# 2. Setup project virtual environment
echo "[2/5] Creating Python virtual environment..."
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$SCRIPT_DIR"

if [ ! -d "venv" ]; then
    python3 -m venv venv
    echo "Virtual environment created in $SCRIPT_DIR/venv"
fi

# 3. Upgrade pip and install pinned requirements
echo "[3/5] Installing dependencies..."
source venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt

# 4. Check .env configuration file
echo "[4/5] Checking configuration..."
if [ ! -f ".env" ]; then
    echo "Creating .env from .env.example..."
    cp .env.example .env
    echo "⚠️ NOTE: Please edit $SCRIPT_DIR/.env to add your API keys!"
else
    echo ".env file already exists."
fi

# 5. Setup systemd service
echo "[5/5] Configuring systemd background service..."
SERVICE_FILE="/etc/systemd/system/binance-square-bot.service"

sudo tee "$SERVICE_FILE" > /dev/null <<EOF
[Unit]
Description=Binance Square Automated Posting Bot - Talha Sniper
After=network.target

[Service]
Type=simple
User=$USER
WorkingDirectory=$SCRIPT_DIR
ExecStart=$SCRIPT_DIR/venv/bin/python main.py
Restart=always
RestartSec=30
EnvironmentFile=$SCRIPT_DIR/.env
StandardOutput=append:$SCRIPT_DIR/logs/systemd.log
StandardError=append:$SCRIPT_DIR/logs/systemd_error.log

[Install]
WantedBy=multi-user.target
EOF

sudo systemctl daemon-reload
sudo systemctl enable binance-square-bot

echo ""
echo "========================================================"
echo " Setup Completed Successfully!"
echo "========================================================"
echo "Next Steps:"
echo " 1. Edit your credentials: nano .env"
echo " 2. Run diagnostics:       python3 scripts/health_check.py"
echo " 3. Start the 24/7 service: sudo systemctl start binance-square-bot"
echo " 4. Monitor live logs:     tail -f logs/square_bot.log"
echo "========================================================"
