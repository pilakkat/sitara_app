#!/bin/bash
# SITARA Robot Client - systemd Deployment Script

set -e

echo "================================================"
echo "SITARA Robot Client - systemd Setup"
echo "================================================"

# Configuration
INSTALL_DIR="/var/www/sitara/client"
CONFIG_DIR="/etc/sitara/robots"
SERVICE_USER="ubuntu"
VENV_DIR="$INSTALL_DIR/.venv"

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# Check if running as root
if [ "$EUID" -ne 0 ]; then 
    echo -e "${RED}ERROR: Please run as root (use sudo)${NC}"
    exit 1
fi

echo ""
echo "Step 1: Creating directories..."
mkdir -p "$INSTALL_DIR"
mkdir -p "$CONFIG_DIR"
chmod 755 "$CONFIG_DIR"

echo ""
echo "Step 2: Creating service user if needed..."
if id "$SERVICE_USER" &>/dev/null; then
    echo -e "${GREEN}✓ User $SERVICE_USER already exists${NC}"
else
    useradd -r -s /bin/bash -d "$INSTALL_DIR" "$SERVICE_USER"
    echo -e "${GREEN}✓ Created user $SERVICE_USER${NC}"
fi

echo ""
echo "Step 3: Setting up Python virtual environment..."
if [ ! -d "$VENV_DIR" ]; then
    sudo -u "$SERVICE_USER" python3 -m venv "$VENV_DIR"
    echo -e "${GREEN}✓ Created virtual environment${NC}"
else
    echo -e "${YELLOW}Virtual environment already exists${NC}"
fi

echo ""
echo "Step 4: Installing Python dependencies..."
sudo -u "$SERVICE_USER" "$VENV_DIR/bin/pip" install --upgrade pip
sudo -u "$SERVICE_USER" "$VENV_DIR/bin/pip" install -r requirements.txt gunicorn
echo -e "${GREEN}✓ Installed dependencies${NC}"

echo ""
echo "Step 5: Copying application files..."
# Copy all Python files
cp *.py "$INSTALL_DIR/"
cp -r templates/ "$INSTALL_DIR/" 2>/dev/null || true
cp -r static/ "$INSTALL_DIR/" 2>/dev/null || true

# Copy config.env as reference (don't overwrite)
if [ ! -f "$INSTALL_DIR/config.env" ]; then
    cp config.env "$INSTALL_DIR/" 2>/dev/null || true
fi

chown -R "$SERVICE_USER:$SERVICE_USER" "$INSTALL_DIR"
echo -e "${GREEN}✓ Copied application files${NC}"

echo ""
echo "Step 6: Installing systemd service..."
cp systemd/sitara-robot@.service /etc/systemd/system/
systemctl daemon-reload
echo -e "${GREEN}✓ Installed systemd service template${NC}"

echo ""
echo "Step 7: Creating robot configuration files..."
for robot_env in systemd/*.env.example; do
    robot_name=$(basename "$robot_env" .env.example)
    target_file="$CONFIG_DIR/$robot_name.env"
    
    if [ -f "$target_file" ]; then
        echo -e "${YELLOW}⚠ $target_file already exists, skipping${NC}"
    else
        cp "$robot_env" "$target_file"
        chmod 600 "$target_file"
        echo -e "${YELLOW}✓ Created $target_file (PLEASE EDIT WITH REAL CREDENTIALS!)${NC}"
    fi
done

echo ""
echo "================================================"
echo -e "${GREEN}Installation Complete!${NC}"
echo "================================================"
echo ""
echo "Next steps:"
echo ""
echo "1. Edit robot configuration files with real credentials:"
echo "   sudo nano $CONFIG_DIR/robot1.env"
echo ""
echo "2. Enable and start robot instances:"
echo "   sudo systemctl enable sitara-robot@robot1"
echo "   sudo systemctl start sitara-robot@robot1"
echo ""
echo "3. Check status:"
echo "   sudo systemctl status sitara-robot@robot1"
echo ""
echo "4. View logs:"
echo "   sudo journalctl -u sitara-robot@robot1 -f"
echo ""
echo "5. For multiple robots, create additional configs:"
echo "   sudo cp $CONFIG_DIR/robot1.env $CONFIG_DIR/robot3.env"
echo "   # Edit robot3.env with unique ROBOT_ID, CLIENT_UI_PORT, etc."
echo "   sudo systemctl enable sitara-robot@robot3"
echo "   sudo systemctl start sitara-robot@robot3"
echo ""
echo "Available robot instances in $CONFIG_DIR:"
ls -1 "$CONFIG_DIR"/*.env 2>/dev/null | sed 's/.*\//  - /' | sed 's/\.env$//' || echo "  (none yet)"
echo ""
