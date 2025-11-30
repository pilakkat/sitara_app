# Software Version Management System

## Overview
This document describes the software version management system implemented for the Sitara robot fleet. The system tracks software versions for 4 controllers on each robot and automatically checks for updates during boot and daily at midnight.

## Robot Controllers
Each robot has 4 independent controllers, each with their own software version:

1. **RCPCU** - Robot Central Processing & Control Unit (Current: v2.3.1)
2. **RCSPM** - Robot Control System & Power Management (Current: v1.8.5)
3. **RCMMC** - Robot Control Motion & Motor Controller (Current: v3.1.2)
4. **RCPMU** - Robot Control Power Management Unit (Current: v1.5.9)

## Features Implemented

### 1. Database Schema (app.py)
Added to the `Robot` model:
- `version_rcpcu` - Software version for RCPCU controller
- `version_rcspm` - Software version for RCSPM controller
- `version_rcmmc` - Software version for RCMMC controller
- `version_rcpmu` - Software version for RCPMU controller
- `last_version_check` - Timestamp of last version check

Default version for new robots: "0.0.0"

### 2. API Endpoints (app.py)

#### GET /api/software/latest_versions
Returns the latest available software versions for all controllers.

**Response:**
```json
{
  "RCPCU": "2.3.1",
  "RCSPM": "1.8.5",
  "RCMMC": "3.1.2",
  "RCPMU": "1.5.9",
  "release_date": "2025-11-28",
  "release_notes": {
    "RCPCU": "Improved navigation algorithms and obstacle detection",
    "RCSPM": "Enhanced power management and battery optimization",
    "RCMMC": "Better motor control precision and torque management",
    "RCPMU": "Updated charging protocols and power distribution"
  }
}
```

#### POST /api/robot/version
Updates the robot's current software versions in the database.

**Request Body:**
```json
{
  "robot_id": 1,
  "versions": {
    "RCPCU": "2.3.1",
    "RCSPM": "1.8.5",
    "RCMMC": "3.1.2",
    "RCPMU": "1.5.9"
  }
}
```

**Response:**
```json
{
  "message": "Robot versions updated successfully",
  "robot_id": 1,
  "versions": {
    "RCPCU": "2.3.1",
    "RCSPM": "1.8.5",
    "RCMMC": "3.1.2",
    "RCPMU": "1.5.9"
  }
}
```

#### Enhanced: GET /api/telemetry
Now includes version information in the telemetry response:

```json
{
  "status": "OPERATIONAL",
  "battery": 12.6,
  "cpu_temp": 45,
  "load": 35,
  "pos_x": 50.0,
  "pos_y": 50.0,
  "cycles": 1234,
  "timestamp": "2025-01-28T12:34:56",
  "versions": {
    "RCPCU": "2.3.1",
    "RCSPM": "1.8.5",
    "RCMMC": "3.1.2",
    "RCPMU": "1.5.9"
  }
}
```

### 3. Client Implementation (client_app.py)

#### Version Tracking
Each robot client maintains its current software versions:
```python
self.versions = {
    'RCPCU': '2.3.1',
    'RCSPM': '1.8.5',
    'RCMMC': '3.1.2',
    'RCPMU': '1.5.9'
}
```

#### Automatic Version Checking
The client checks for software updates:
1. **During boot sequence** - Immediately after starting
2. **Daily at midnight** - Between 00:00 and 00:59 UTC

#### Version Check Logic (`check_software_updates()`)
1. Fetches latest versions from server
2. Compares each controller version
3. Logs update availability
4. Sends current versions to server

#### Version Reporting (`send_version_info()`)
Sends current versions to the server via POST /api/robot/version endpoint.

#### Daily Check Trigger (`should_check_versions()`)
Returns `True` if:
- It's the first version check (boot sequence)
- Current hour is 00 (midnight) and last check was not today

### 4. Dashboard Display (dashboard.html)

Added a new "SOFTWARE VERSIONS" panel in the status sidebar showing:
- RCPCU (Central Control)
- RCSPM (Power Mgmt)
- RCMMC (Motor Control)
- RCPMU (Power Unit)

All versions are displayed in real-time and updated via telemetry.

### 5. Frontend Updates (main.js)

Enhanced `updateTelemetryDisplay()` function to update version displays:
```javascript
if (data.versions) {
    $('#versionRCPCU').text(data.versions.RCPCU || '--');
    $('#versionRCSPM').text(data.versions.RCSPM || '--');
    $('#versionRCMMC').text(data.versions.RCMMC || '--');
    $('#versionRCPMU').text(data.versions.RCPMU || '--');
}
```

## Setup Instructions

### 1. Reinitialize Database
The new version columns need to be added to the database:

```powershell
python init_db.py
```

This will create the new columns with default values ("0.0.0").

### 2. Update Seed Data (Optional)
If you want to populate test data with specific versions, modify `seed_data.py` to set initial versions when creating robots.

### 3. Start the Server
```powershell
python app.py
```

### 4. Start Robot Clients
Each robot client will automatically:
1. Check for updates during boot
2. Send its current versions to the server
3. Check for updates daily at midnight

Example:
```powershell
cd client
python client_app.py 1 http://localhost:5000 office_floor_1 5001
```

## Testing the System

### Manual Version Check
You can test the version endpoints using curl or Postman:

```powershell
# Get latest versions
curl http://localhost:5000/api/software/latest_versions

# Get current telemetry (includes versions)
curl http://localhost:5000/api/telemetry?robot_id=1
```

### Verify Dashboard Display
1. Log in to the dashboard
2. Select a robot
3. Check the "SOFTWARE VERSIONS" panel in the status sidebar
4. Versions should display as the robot sends telemetry

### Check Logs
Watch the client console output for version check messages:
```
[ROBOT-1] Boot sequence: Checking for software updates...
[ROBOT-1] Fetching latest software versions from server...
[ROBOT-1] Software version check complete. All controllers are up to date.
[ROBOT-1] Sending version information to server...
[ROBOT-1] Version information sent successfully
```

## Version Update Workflow

When new software versions are available:

1. **Update Latest Versions** - Modify the hardcoded versions in `app.py` at the `/api/software/latest_versions` endpoint
2. **Deploy New Software** - Update the actual controller software on robots
3. **Update Client Versions** - Modify the version numbers in `client_app.py`
4. **Restart Robot** - The robot will check for updates during boot
5. **Verify Dashboard** - Check that dashboard shows new versions

## Future Enhancements

Consider these improvements:
- Store latest versions in database or config file instead of hardcoding
- Add software update page in dashboard UI
- Implement automatic download and installation
- Add version history tracking
- Create update approval workflow
- Add rollback capability
- Implement staged rollouts (update subset of fleet first)
- Add update status tracking (pending, in-progress, completed, failed)

## Configuration

### Changing Update Check Time
To modify the midnight check time, edit `should_check_versions()` in `client_app.py`:
```python
current_hour = datetime.now().hour
# Change 0 to desired hour (0-23)
if current_hour == 0:  # Midnight check
```

### Changing Version Check Frequency
To modify how often the system checks if it's time to update:
```python
# In run_telemetry_loop(), change sleep duration
time.sleep(5)  # Check every 5 seconds
```

## Troubleshooting

### Versions Not Updating on Dashboard
1. Check browser console for JavaScript errors
2. Verify telemetry API includes versions: `curl http://localhost:5000/api/telemetry?robot_id=1`
3. Refresh the dashboard page
4. Check that jQuery selectors match element IDs in HTML

### Robot Not Checking for Updates
1. Verify robot client is running
2. Check client console logs for version check messages
3. Ensure server URL is correct in client startup
4. Verify network connectivity between client and server

### Database Errors
1. Delete `database/sitara.db` and reinitialize: `python init_db.py`
2. Check that all models are imported in `init_db.py`
3. Verify SQLAlchemy is installed: `pip install -r requirements.txt`

## API Documentation

See the full API specification in the main application documentation.

---

*Last Updated: 2025-01-28*
*Version Management System: v1.0*
