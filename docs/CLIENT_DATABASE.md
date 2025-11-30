# Client Database System

## Overview

The SITARA client now includes a local SQLite database to track:
- Robot configuration and software versions
- User credentials
- Software update history
- Available updates from the server

## Database Schema

### Tables

1. **user** - Stores client user credentials
   - `id` (INTEGER, PRIMARY KEY)
   - `username` (TEXT, UNIQUE)
   - `password` (TEXT)
   - `created_at` (TIMESTAMP)

2. **robot** - Stores robot configuration
   - `id` (INTEGER, PRIMARY KEY)
   - `serial_number` (TEXT, UNIQUE)
   - `model_type` (TEXT, default "32DOF-HUMANOID")
   - `assigned_user_id` (INTEGER, FOREIGN KEY → user.id)
   - `version_rcpcu` (TEXT) - Robot Central Processing & Control Unit version
   - `version_rcspm` (TEXT) - Robot Control System & Power Management version
   - `version_rcmmc` (TEXT) - Robot Control Motion & Motor Controller version
   - `version_rcpmu` (TEXT) - Robot Control Power Management Unit version
   - `last_version_check` (TIMESTAMP)
   - `created_at` (TIMESTAMP)
   - `updated_at` (TIMESTAMP)

3. **software_versions** - Tracks current and available software versions
   - `id` (INTEGER, PRIMARY KEY)
   - `component` (TEXT) - Controller name (RCPCU, RCSPM, RCMMC, RCPMU)
   - `current_version` (TEXT) - Currently installed version
   - `available_version` (TEXT) - Latest available version from server
   - `release_date` (TEXT)
   - `release_notes` (TEXT)
   - `update_pending` (INTEGER) - 1 if update available, 0 if up-to-date
   - `last_checked` (TIMESTAMP)
   - `updated_at` (TIMESTAMP)

4. **version_history** - Audit log of software updates
   - `id` (INTEGER, PRIMARY KEY)
   - `robot_id` (INTEGER, FOREIGN KEY → robot.id)
   - `component` (TEXT)
   - `old_version` (TEXT)
   - `new_version` (TEXT)
   - `updated_at` (TIMESTAMP)

## Setup

### First Time Setup

1. Navigate to the client directory:
   ```bash
   cd client
   ```

2. Run the database setup script:
   ```bash
   # Windows
   setup_database.bat
   
   # Linux/Mac
   python init_client_db.py
   ```

3. The script will:
   - Create the `database/` directory
   - Initialize `client.db` with all tables
   - Seed initial data from your `.env` file

### Manual Setup

If you prefer manual setup:

```bash
# Initialize database structure
python init_client_db.py

# Seed data for a specific robot
python init_client_db.py <robot_id> <username> <password>

# Example:
python init_client_db.py 1 deepak mypassword
```

## Features

### Software Version Management

#### Check for Updates
The client automatically checks for updates:
- **During boot sequence** - When client starts
- **Daily at midnight** - Automatic background check
- **Manual check** - Via the web interface

#### Update Workflow

1. **Server Publishes Update**
   - Server maintains latest versions in `/api/software/latest_versions`
   - Includes version numbers, release dates, and notes

2. **Client Checks for Updates**
   - Client queries server for latest versions
   - Compares with current installed versions
   - Saves available updates to local database
   - Marks updates as "pending" if newer version available

3. **User Reviews Updates**
   - Opens control interface (http://localhost:5002)
   - Clicks "🔍 CHECK FOR UPDATES" button
   - Reviews available updates with release notes

4. **User Opts-In to Update**
   - Clicks "📥 INSTALL UPDATE" for desired component
   - Update is applied to local database
   - New version is sent to server in next telemetry
   - Version history is recorded

#### Simulated Update Process

Since this is a simulation, "installing" an update:
1. Updates the `software_versions` table (current_version)
2. Updates the `robot` table (version_* columns)
3. Records change in `version_history` table
4. Updates in-memory version in `robot_client.versions`
5. Sends updated version to server via `send_version_info()`
6. Server records new version in its database

## API Endpoints

### Version Management

- **GET** `/api/versions/status`
  - Returns current versions and available updates
  - Response includes version history

- **POST** `/api/versions/check`
  - Triggers manual version check against server
  - Returns pending updates

- **POST** `/api/versions/update`
  - Applies a software update
  - Body: `{"component": "RCPCU"}`
  - Returns update confirmation

## Database Location

- **Path**: `client/database/client.db`
- **Format**: SQLite 3
- **Size**: ~10-20 KB (typical)

## Database Manager Class

The `ClientDatabase` class provides all database operations:

```python
from client_database import ClientDatabase

db = ClientDatabase()

# Get robot versions
versions = db.get_robot_versions(robot_id=1)
# {'RCPCU': '2.3.1', 'RCSPM': '1.8.5', ...}

# Check for pending updates
updates = db.get_pending_updates()

# Apply an update
db.apply_software_update(robot_id=1, component='RCPCU', new_version='2.4.0')

# View update history
history = db.get_version_history(robot_id=1, limit=10)
```

## Web Interface

### Software Updates Tab

The control interface now includes a "🔄 Software Updates" section:

1. **Check for Updates Button**
   - Manually trigger version check
   - Queries server for latest versions
   - Displays available updates

2. **Update Cards**
   - Shows component name (RCPCU, RCSPM, etc.)
   - Displays current → available version
   - Shows release notes
   - Provides "INSTALL UPDATE" button

3. **Update Process**
   - Click install button
   - Simulated installation (instant)
   - Success confirmation
   - Version reflected in telemetry

## Version Synchronization

### Client → Server

When telemetry is sent, it includes current versions:
```json
{
  "robot_id": 1,
  "battery_voltage": 24.5,
  "version_rcpcu": "2.3.1",
  "version_rcspm": "1.8.5",
  "version_rcmmc": "3.1.2",
  "version_rcpmu": "1.5.9"
}
```

Server stores these in its `robots` table.

### Server → Client

Client queries server for latest versions:
```json
{
  "RCPCU": "2.4.0",
  "RCSPM": "1.9.0",
  "RCMMC": "3.2.0",
  "RCPMU": "1.6.0",
  "release_date": "2025-12-01",
  "release_notes": {
    "RCPCU": "Performance improvements",
    ...
  }
}
```

Client compares and stores in `software_versions` table.

## Maintenance

### Backup Database

```bash
# Windows
copy database\client.db database\client_backup.db

# Linux/Mac
cp database/client.db database/client_backup.db
```

### Reset Database

```bash
# Delete database
rm database/client.db

# Reinitialize
python init_client_db.py
python init_client_db.py 1 deepak password
```

### Query Database Manually

```bash
sqlite3 database/client.db

# Show tables
.tables

# View robot info
SELECT * FROM robot;

# View current versions
SELECT * FROM software_versions;

# View update history
SELECT * FROM version_history ORDER BY updated_at DESC LIMIT 10;

# Exit
.quit
```

## Troubleshooting

### Database Not Found

If you see `[DB] Database not found`:
1. Run `setup_database.bat` (Windows) or `python init_client_db.py`
2. Ensure you're in the `client/` directory
3. Check that `database/` directory was created

### Version Not Updating

If versions don't update after installation:
1. Check console for error messages
2. Verify authentication is successful
3. Ensure server is running
4. Check database with SQLite:
   ```bash
   sqlite3 database/client.db "SELECT * FROM software_versions;"
   ```

### Credentials Not Working

If authentication fails:
1. Verify `.env` file has correct credentials
2. Re-run database setup: `setup_database.bat`
3. Check user table:
   ```bash
   sqlite3 database/client.db "SELECT * FROM user;"
   ```

## Future Enhancements

Potential improvements:
- [ ] Download actual firmware files
- [ ] Verify update checksums
- [ ] Rollback functionality
- [ ] Automated update scheduling
- [ ] Multi-stage updates (test → production)
- [ ] Update notifications/alerts
- [ ] Bandwidth throttling for downloads
- [ ] Delta updates (only changed bytes)
