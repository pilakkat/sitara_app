# systemd Deployment Guide

## Quick Start

### 1. Install the service
```bash
cd /home/deepak/Downloads/sitara_app/client
sudo systemd/install.sh
```

### 2. Configure robot credentials
```bash
sudo nano /etc/sitara/robots/robot1.env
```

Edit these values:
```bash
ROBOT_USERNAME=robot1
ROBOT_PASSWORD=your_actual_password
CLIENT_UI_PORT=5002
```

### 3. Start the service
```bash
sudo systemctl enable sitara-robot@robot1
sudo systemctl start sitara-robot@robot1
sudo systemctl status sitara-robot@robot1
```

### 4. View logs
```bash
sudo journalctl -u sitara-robot@robot1 -f
```

## Multiple Robot Instances

### Setup Robot 2
```bash
# Copy config template
sudo cp /etc/sitara/robots/robot1.env /etc/sitara/robots/robot2.env

# Edit with unique values
sudo nano /etc/sitara/robots/robot2.env
```

**Important:** Each robot MUST have unique:
- `ROBOT_ID` (e.g., 1, 2, 3)
- `CLIENT_UI_PORT` (e.g., 5002, 5003, 5004)
- `ROBOT_USERNAME` (optional but recommended)

```bash
# Start robot 2
sudo systemctl enable sitara-robot@robot2
sudo systemctl start sitara-robot@robot2
```

### Manage Multiple Robots
```bash
# Start all
sudo systemctl start sitara-robot@robot1 sitara-robot@robot2 sitara-robot@robot3

# Stop all
sudo systemctl stop sitara-robot@robot{1..3}

# Check status of all
systemctl status 'sitara-robot@*'

# View logs from all
sudo journalctl -u 'sitara-robot@*' -f
```

## File Structure

```
/var/www/sitara/client/          # Application directory
├── .venv/                        # Python virtual environment
├── client_app.py                 # Main application
├── wsgi.py                       # WSGI entry point
├── config.env                    # Default config (optional)
└── ...

/etc/sitara/robots/               # Robot configurations
├── robot1.env                    # Robot 1 config
├── robot2.env                    # Robot 2 config
└── robot3.env                    # Robot 3 config

/etc/systemd/system/              # systemd services
└── sitara-robot@.service        # Service template
```

## Service Template Explained

```ini
[Unit]
Description=SITARA Robot Client - Instance %i
After=network.target

[Service]
Type=notify                       # Gunicorn supports notify
User=ubuntu                       # Run as ubuntu user
WorkingDirectory=/var/www/sitara/client

# Load robot-specific config
EnvironmentFile=/etc/sitara/robots/%i.env

# CRITICAL: --workers 1 (only one robot instance per service)
ExecStart=/var/www/sitara/client/.venv/bin/gunicorn \
    --workers 1 \
    --threads 2 \
    --bind 0.0.0.0:${CLIENT_UI_PORT} \
    client_app:control_app

Restart=always
```

The `%i` is replaced by the instance name:
- `sitara-robot@robot1` → loads `/etc/sitara/robots/robot1.env`
- `sitara-robot@robot2` → loads `/etc/sitara/robots/robot2.env`

## Why Use --workers 1?

**Critical:** Each gunicorn worker creates a separate Python process with its own robot client instance. Using `--workers 2` would create:
- 2 robot clients with the same `ROBOT_ID`
- Both trying to connect to the server
- Both sending telemetry (duplicates)
- Both trying to execute commands (conflicts)

**Solution:** Always use `--workers 1` and `--threads 2` for concurrency.

## Configuration Priority

With systemd, environment variables are loaded in this order:

1. **EnvironmentFile** (`/etc/sitara/robots/*.env`) - **Highest Priority**
2. `.env` file in application directory (if exists)
3. `config.env` file in application directory (if exists)
4. Hardcoded defaults in code

The code now uses `load_dotenv(override=False)` which means:
- System environment variables (from EnvironmentFile) take precedence
- .env/.config.env only fill in missing values

## Troubleshooting

### Service won't start
```bash
# Check status
sudo systemctl status sitara-robot@robot1

# View detailed logs
sudo journalctl -u sitara-robot@robot1 -n 50 --no-pager

# Check config file
sudo cat /etc/sitara/robots/robot1.env
```

### Port already in use
```bash
# Find what's using the port
sudo lsof -i :5002

# Change port in config
sudo nano /etc/sitara/robots/robot1.env
# Set CLIENT_UI_PORT=5010

# Restart service
sudo systemctl restart sitara-robot@robot1
```

### Permission denied
```bash
# Fix ownership
sudo chown -R ubuntu:ubuntu /var/www/sitara/client

# Fix config permissions
sudo chmod 600 /etc/sitara/robots/*.env
```

### Robot not authenticating
- Check credentials in `/etc/sitara/robots/robot1.env`
- Ensure `ROBOT_USERNAME` and `ROBOT_PASSWORD` match server database
- Check server is running: `curl http://127.0.0.1:5001`

## Updating the Application

```bash
# Stop service
sudo systemctl stop sitara-robot@robot1

# Update code
cd /var/www/sitara/client
sudo -u ubuntu git pull  # if using git
# or copy new files manually

# Update dependencies
sudo -u ubuntu .venv/bin/pip install -r requirements.txt

# Start service
sudo systemctl start sitara-robot@robot1
```

## Monitoring

### Real-time logs
```bash
sudo journalctl -u sitara-robot@robot1 -f
```

### Check all robot services
```bash
systemctl list-units 'sitara-robot@*'
```

### Resource usage
```bash
systemctl status sitara-robot@robot1
```

## Security Notes

The service template includes hardening:
- `NoNewPrivileges=true` - Prevent privilege escalation
- `PrivateTmp=true` - Isolated /tmp directory
- `ProtectSystem=strict` - Read-only system directories
- `ProtectHome=true` - No access to home directories
- `ReadWritePaths=/var/www/sitara/client` - Only app directory writable

Configuration files should be secure:
```bash
sudo chmod 600 /etc/sitara/robots/*.env
sudo chown root:root /etc/sitara/robots/*.env
```

## Do You Still Need the Code Changes?

**YES**, because:

1. **Absolute paths** - Work regardless of WorkingDirectory
2. **Module-level config** - Loaded when gunicorn imports, before workers fork
3. **Safe import** - Module loads even with missing credentials (logs errors clearly)
4. **Flexible priority** - `override=False` lets EnvironmentFile take precedence
5. **Better error handling** - Clear messages about what's wrong

The systemd setup **complements** the code changes, but doesn't replace them.
