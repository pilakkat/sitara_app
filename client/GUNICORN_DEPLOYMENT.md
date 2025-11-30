# Gunicorn Deployment Guide

## Overview

The SITARA Robot Client has been refactored to be safe for deployment with gunicorn. Environment variables are now loaded at module level with absolute paths, making it compatible with production WSGI servers.

## Key Changes

### 1. Environment Variable Loading
- **Before**: Environment variables were loaded at module level but only accessed in `main()`
- **After**: All configuration is loaded at module level using absolute paths
- **Benefit**: Works correctly regardless of working directory (important for gunicorn)

### 2. Configuration Files
The application looks for configuration in this order:
1. `.env` file (personal credentials, git-ignored)
2. `config.env` file (defaults and templates)
3. Environment variables (set by system/docker/gunicorn)

All file paths are now resolved relative to the script location:
```python
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
env_file = os.path.join(SCRIPT_DIR, '.env')
config_file = os.path.join(SCRIPT_DIR, 'config.env')
```

### 3. Module-Level Configuration
All configuration variables are now available at module level:
- `SERVER_URL`
- `USERNAME` (from `ROBOT_USERNAME` env var)
- `PASSWORD` (from `ROBOT_PASSWORD` env var)
- `ROBOT_ID`
- `UI_PORT`

### 4. Safe Import Behavior
- The module can be imported without errors even if credentials are missing
- Missing credentials log warnings but don't cause import failures
- This allows gunicorn to import the module successfully

## Running with Gunicorn

### Option 1: Using the WSGI Entry Point
```bash
cd /home/$user/Downloads/sitara_app/client
gunicorn wsgi:app -b 0.0.0.0:5002 --workers 1
```

### Option 2: Using the Configuration File
```bash
cd /home/$user/Downloads/sitara_app/client
gunicorn -c gunicorn.conf.py wsgi:app
```

### Option 3: Direct Module Reference
```bash
cd /home/$user/Downloads/sitara_app/client
gunicorn client_app:control_app -b 0.0.0.0:5001 --workers 1
```

## Environment Variables

Set these environment variables before running gunicorn:

```bash
export ROBOT_USERNAME="your_username"
export ROBOT_PASSWORD="your_password"
export ROBOT_ID=1
export SERVER_URL="http://127.0.0.1:5001"
export CLIENT_UI_PORT=5001
```

Or create a `.env` file in the `client` directory:
```
ROBOT_USERNAME=your_username
ROBOT_PASSWORD=your_password
ROBOT_ID=1
SERVER_URL=http://127.0.0.1:5001
CLIENT_UI_PORT=5001
```

## Important Notes

### Working Directory
The application now uses absolute paths, so it works correctly regardless of the current working directory:
```bash
# These all work the same:
cd /home/$user/Downloads/sitara_app/client && gunicorn wsgi:app
cd /home/$user/Downloads/sitara_app && gunicorn client.wsgi:app
cd / && gunicorn -c /path/to/client/gunicorn.conf.py wsgi:app
```

### Worker Count
**Always use `--workers 1`** for the robot client to avoid multiple instances:
```bash
gunicorn wsgi:app -b 0.0.0.0:5001 --workers 1
```

Multiple workers would create multiple robot client instances, causing conflicts.

### Background Threads
The robot client runs telemetry and command loops in background threads. These are started when `initialize_robot_client()` is called in `wsgi.py`.

### Standalone Execution
The application still works as a standalone script:
```bash
python client_app.py
```

## Configuration Priority

1. **Command line arguments** (highest priority, standalone mode only)
2. **Environment variables** (system/shell)
3. **`.env` file** (personal credentials)
4. **`config.env` file** (defaults/templates)

## Troubleshooting

### "Missing credentials" error
- Check that `.env` or `config.env` exists in the `client` directory
- Ensure `ROBOT_USERNAME` and `ROBOT_PASSWORD` are set
- Verify file permissions allow reading

### "File not found" errors
- The application now uses absolute paths, so this should be rare
- Check that `.env` or `config.env` exists in the same directory as `client_app.py`

### Robot client not responding
- Check the logs for initialization errors
- Verify the `SERVER_URL` is correct
- Ensure only 1 gunicorn worker is running

### Port conflicts
- The default UI port is 5002
- Change it with: `export CLIENT_UI_PORT=8080`
- Or in the `.env` file: `CLIENT_UI_PORT=8080`

## Docker Deployment

Example Dockerfile:
```dockerfile
FROM python:3.11-slim

WORKDIR /app
COPY client/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt gunicorn

COPY client/ .

ENV ROBOT_USERNAME=robot1
ENV ROBOT_PASSWORD=password123
ENV ROBOT_ID=1
ENV SERVER_URL=http://server:5001
ENV CLIENT_UI_PORT=5001

EXPOSE 5001

CMD ["gunicorn", "-c", "gunicorn.conf.py", "wsgi:app"]
```

## systemd Service

Example systemd service file:
```ini
[Unit]
Description=SITARA Robot Client
After=network.target

[Service]
Type=notify
User=sitara
WorkingDirectory=/opt/sitara/client
Environment="ROBOT_USERNAME=robot1"
Environment="ROBOT_PASSWORD=password123"
Environment="ROBOT_ID=1"
Environment="SERVER_URL=http://localhost:5001"
ExecStart=/usr/local/bin/gunicorn -c gunicorn.conf.py wsgi:app
Restart=always

[Install]
WantedBy=multi-user.target
```

## Summary

The refactored application is now production-ready:
- ✅ Works with gunicorn
- ✅ Uses absolute paths (working directory independent)
- ✅ Loads config at module level
- ✅ Safe import behavior
- ✅ Maintains backward compatibility with standalone execution
- ✅ Comprehensive logging
- ✅ Proper error handling
