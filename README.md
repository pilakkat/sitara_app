# SITARA Robot Fleet Management System

## 📚 Documentation Index

### Main Documentation
- **[README.md](README.md)** - Main project documentation (this file)
- **[VERSION_MANAGEMENT_GUIDE.md](VERSION_MANAGEMENT_GUIDE.md)** - Software version tracking and management guide
- **[BATTERY_DISPLAY_UPDATE.md](BATTERY_DISPLAY_UPDATE.md)** - Battery display implementation details

### Client Documentation
- **[client/README.md](client/README.md)** - Robot client application setup and usage
- **[client/ARCHITECTURE.md](client/ARCHITECTURE.md)** - Client architecture and design patterns
- **[client/CREDENTIALS.md](client/CREDENTIALS.md)** - Credential configuration and security
- **[client/GUNICORN_DEPLOYMENT.md](client/GUNICORN_DEPLOYMENT.md)** - Production deployment with Gunicorn
- **[client/systemd/README.md](client/systemd/README.md)** - SystemD service configuration

---

## Overview

SITARA is a comprehensive robot fleet management system that provides real-time telemetry monitoring, spatial mapping (SLAM), and remote control capabilities for humanoid robots. The system features a modern web dashboard with cyberpunk aesthetics, real-time data visualization, and multi-robot management capabilities.

## Features

### Core Capabilities
- **Real-Time Telemetry Monitoring** - Live battery, temperature, motor load, and status tracking
- **Spatial Mapping (SLAM)** - Visual robot positioning with obstacle detection and path history
- **Multi-Robot Management** - Support for multiple robots with user-based access control
- **Remote Control** - Web-based directional control and command interface
- **Software Version Management** - Track and monitor software versions across 4 robot controllers
- **Historical Data Playback** - Time-travel through recorded robot data with timeline scrubber
- **Battery Management** - Visual battery indicator with percentage-based display
- **Obstacle Management** - Robot-specific workspaces with configurable boundaries

### Dashboard Features
- Live telemetry updates every 5 seconds
- Interactive map with robot marker and path visualization
- Battery and temperature history charts
- Software version display for all controllers
- Timeline scrubber for historical data replay
- Live/Historical mode switching
- Multi-date data browsing

## Architecture

### System Components

```
┌─────────────────────────────────────────────────────────────┐
│                     SITARA Architecture                     │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  ┌──────────────┐         ┌──────────────┐                  │
│  │   Browser    │◄────────┤  Flask Web   │                  │
│  │  Dashboard   │  HTTP   │  Application │                  │
│  │  (HTML/JS)   │────────►│   (app.py)   │                  │
│  └──────────────┘         └───────┬──────┘                  │
│                                   │                         │
│                                   │ SQLAlchemy              │
│                                   ▼                         │
│                            ┌──────────────┐                 │
│                            │   SQLite     │                 │
│                            │   Database   │                 │
│                            └──────────────┘                 │
│                                   ▲                         │
│                                   │ REST API                │
│  ┌──────────────┐         ┌───────┴───────┐                 │
│  │    Robot     │────────►│ Robot Client  │                 │
│  │  Hardware    │  Serial │ Application   │                 │
│  │   (Simul.)   │◄────────│(client_app.py)│                 │
│  └──────────────┘         └───────────────┘                 │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

### Technology Stack

**Backend:**
- Python 3.x
- Flask - Web framework
- Flask-Login - User authentication
- SQLAlchemy - ORM for database operations
- SQLite - Database storage

**Frontend:**
- HTML5/CSS3
- JavaScript (ES6+)
- jQuery - DOM manipulation and AJAX
- Chart.js - Data visualization
- Bootstrap 5 - UI framework (customized)

**Robot Client:**
- Python 3.x
- Requests - HTTP client
- Flask - Control interface
- Threading - Concurrent operations
  
**Note: Client control is only for demo purpose. In reality, this must be handled from the Robot Hardware side**

## Installation

### Prerequisites
- Python 3.8 or higher
- pip (Python package manager)
- Modern web browser (Chrome, Firefox, Edge)

### Setup Instructions

1. **Clone the Repository**
   ```bash
   git clone <repository-url>
   cd sitara_app
   ```

2. **Install Dependencies**
   ```bash
   pip install -r requirements.txt
   ```

3. **Configure Environment Variables**
   Create a `.env` file in the root directory:
   ```env
   SECRET_KEY=your-secret-key-here
   DATABASE_URL=sqlite:///database/sitara.db
   ADMIN_USERNAME=admin
   ADMIN_PASSWORD=your-admin-password
   OPERATOR_USERNAME=operator
   OPERATOR_PASSWORD=your-operator-password
   ```

4. **Initialize Database**
   ```bash
   python init_db.py
   ```

5. **Seed Sample Data (Optional: Random data to visualize history)**
   ```bash
   python seed_data.py
   ```

6. **Start the Server**
   ```bash
   python app.py
   ```
   Server will start at `http://localhost:5000`

7. **Start Robot Client(s) - for demo**
   ```bash
   cd client
   python client_app.py [robot_id] [username] [password] [control_port]
   ```
   Example:
   ```bash
   python client_app.py 1 operator operator_password 5001
   ```

## Configuration

### Robot Client Configuration

The robot client can be configured via:
1. Command-line arguments
2. Environment variables (`.env` file in client folder)
3. Configuration file (`config.env`)

**Client Environment Variables:**
```env
SERVER_URL=http://localhost:5000
ROBOT_USERNAME=operator
ROBOT_PASSWORD=operator_password
ROBOT_ID=1
CLIENT_UI_PORT=5001
```

## Database Schema

### Tables

#### 1. **User**
- `id` - Primary key
- `username` - Unique username
- `password` - Password (should be hashed in production)

#### 2. **Robot**
- `id` - Primary key
- `serial_number` - Unique robot identifier
- `model_type` - Robot model (e.g., "32DOF-HUMANOID")
- `assigned_to` - Foreign key to User
- `version_rcpcu` - RCPCU controller version
- `version_rcspm` - RCSPM controller version
- `version_rcmmc` - RCMMC controller version
- `version_rcpmu` - RCPMU controller version
- `last_version_check` - Last software version check timestamp

#### 3. **TelemetryLog**
- `id` - Primary key
- `robot_id` - Foreign key to Robot
- `timestamp` - Data timestamp (indexed)
- `battery_voltage` - Battery voltage (V)
- `cpu_temp` - CPU temperature (°C)
- `motor_load` - Motor load percentage
- `cycle_counter` - Operation cycle count
- `status_code` - Robot status

#### 4. **PathLog**
- `id` - Primary key
- `robot_id` - Foreign key to Robot
- `timestamp` - Position timestamp (indexed)
- `pos_x` - X position (0-100%)
- `pos_y` - Y position (0-100%)
- `orientation` - Heading in degrees (0-360°)

#### 5. **Obstacle**
- `id` - Primary key
- `robot_id` - Foreign key to Robot
- `name` - Obstacle name
- `obstacle_type` - Type: "rectangle", "circle"
- `x`, `y` - Position (0-100%)
- `width`, `height` - Dimensions for rectangles
- `radius` - Radius for circles
- `color` - Visual styling color

## API Reference

### Authentication APIs

#### POST `/login`
Login to the system
- **Form Data:**
  - `username` - User's username
  - `password` - User's password
- **Response:** Redirect to dashboard or login page
- **Status:** 200 (success), 401 (unauthorized)

#### GET `/logout`
Logout from the system
- **Response:** Redirect to login page

### Robot Management APIs

#### GET `/api/robots`
Get list of accessible robots for current user
- **Authentication:** Required
- **Response:**
  ```json
  [
    {
      "id": 1,
      "serial_number": "SITARA-001",
      "model_type": "32DOF-HUMANOID",
      "status": "OPERATIONAL"
    }
  ]
  ```

#### GET `/api/robot/date_range`
Get available date range for robot data
- **Query Parameters:**
  - `robot_id` - Robot ID
- **Response:**
  ```json
  {
    "earliest": "2025-11-01",
    "latest": "2025-11-30"
  }
  ```

### Telemetry APIs

#### GET `/api/telemetry`
Get current/latest telemetry data
- **Authentication:** Required
- **Query Parameters:**
  - `robot_id` - Robot ID (optional, defaults to first accessible)
- **Response:**
  ```json
  {
    "robot_id": 1,
    "serial_number": "SITARA-001",
    "battery": 24.5,
    "battery_percent": 86.5,
    "cpu_temp": 45,
    "load": 35,
    "status": "OPERATIONAL",
    "pos_x": 50.0,
    "pos_y": 50.0,
    "orientation": 0.0,
    "cycles": 1234,
    "timestamp": "2025-11-30T12:34:56",
    "versions": {
      "RCPCU": "2.3.1",
      "RCSPM": "1.8.5",
      "RCMMC": "3.1.2",
      "RCPMU": "1.5.9"
    }
  }
  ```

#### POST `/api/robot/telemetry`
Submit telemetry data from robot
- **Authentication:** Required
- **JSON Body:**
  ```json
  {
    "robot_id": 1,
    "battery_voltage": 24.5,
    "temperature": 45,
    "motor_load": 35,
    "status": "OPERATIONAL",
    "cycle_count": 1234,
    "x": 50.0,
    "y": 50.0,
    "orientation": 0.0,
    "timestamp": "2025-11-30T12:34:56"
  }
  ```
- **Response:** `{"status": "ok"}`

#### GET `/api/telemetry_history`
Get historical telemetry logs
- **Query Parameters:**
  - `robot_id` - Robot ID
  - `date` - Date in YYYY-MM-DD format (optional)
  - `since` - Get logs after this timestamp (optional)
- **Response:** Array of telemetry log entries

#### GET `/api/telemetry_chart_data`
Get telemetry data formatted for Chart.js
- **Query Parameters:**
  - `robot_id` - Robot ID
  - `date` - Date for historical data (optional)
  - `hours` - Number of hours to fetch (default: 1)
- **Response:**
  ```json
  {
    "labels": ["12:00:00", "12:05:00", ...],
    "battery": [24.5, 24.4, ...],
    "temperature": [45, 46, ...]
  }
  ```

### Path & Position APIs

#### GET `/api/path_history`
Get robot's movement path history
- **Query Parameters:**
  - `robot_id` - Robot ID
  - `date` - Date for historical data (optional)
  - `since` - Get path after this timestamp (incremental)
- **Response:**
  ```json
  [
    {
      "x": 50.0,
      "y": 50.0,
      "timestamp": "2025-11-30T12:34:56"
    }
  ]
  ```

### Command APIs

#### GET `/api/robot/commands`
Robot polls for new commands
- **Authentication:** Required
- **Query Parameters:**
  - `robot_id` - Robot ID
- **Response:**
  ```json
  [
    {
      "command": "move_up",
      "timestamp": "2025-11-30T12:34:56"
    }
  ]
  ```

#### POST `/api/robot/command`
Send command to robot (from dashboard)
- **Authentication:** Required
- **JSON Body:**
  ```json
  {
    "robot_id": 1,
    "command": "move_up"
  }
  ```
- **Commands:** `move_up`, `move_down`, `move_left`, `move_right`, `stop`, `scan_area`
- **Response:** `{"status": "queued"}`

### Obstacle APIs

#### GET `/api/obstacles`
Get obstacles for robot's workspace
- **Query Parameters:**
  - `robot_id` - Robot ID (optional)
- **Response:**
  ```json
  [
    {
      "id": 1,
      "name": "Conference Table",
      "type": "rectangle",
      "x": 15,
      "y": 35,
      "width": 25,
      "height": 30,
      "color": "rgba(100,100,100,0.4)"
    }
  ]
  ```

### Software Version APIs

#### GET `/api/software/latest_versions`
Get latest available software versions
- **Response:**
  ```json
  {
    "RCPCU": "2.3.1",
    "RCSPM": "1.8.5",
    "RCMMC": "3.1.2",
    "RCPMU": "1.5.9",
    "release_date": "2025-11-28",
    "release_notes": {
      "RCPCU": "Improved navigation algorithms",
      "RCSPM": "Enhanced power management",
      "RCMMC": "Better motor control precision",
      "RCPMU": "Updated charging protocols"
    }
  }
  ```

#### POST `/api/robot/version`
Update robot's software version information
- **JSON Body:**
  ```json
  {
    "robot_id": 1,
    "version_rcpcu": "2.3.1",
    "version_rcspm": "1.8.5",
    "version_rcmmc": "3.1.2",
    "version_rcpmu": "1.5.9"
  }
  ```
- **Response:** `{"message": "Robot versions updated successfully"}`

## Robot Controllers

The system tracks software versions for 4 independent controllers on each robot:

1. **RCPCU** - Robot Central Processing & Communication Unit
   - Main processing and decision-making
   - Navigation algorithms
   - Communication protocols

2. **RCSPM** - Robot Sensory and Perception Management
   - Process information from various sensors including camera 
   - Visual processing using AI

3. **RCMMC** - Robot Mobility & Manipulation Controller
   - Motor control and coordination
   - Movement precision
   - Torque management

4. **RCPMU** - Robot Control Power Management Unit
   - Charging protocols
   - Power distribution
   - Energy efficiency

## Robot Status Codes

- **STANDBY** - Robot is idle and ready
- **MOVING** - Robot is in motion
- **SCANNING** - Robot is performing area scan
- **CHARGING** - Robot is charging
- **FAULT** - System fault detected
- **OFFLINE** - Robot is powered off
- **BOOTING** - Robot is starting up
- **OPERATIONAL** - Normal operation (alias for STANDBY)
- **BAT LOW** - Battery low warning (appended to status)

## Battery Management

### Voltage to Percentage Conversion
The system uses a 24V Li-ion 6S battery system:
- **Fully Charged:** 25.2V (100%)
- **Nominal:** 24.5V (86.5%)
- **Low Battery:** 22.0V (38%) - Warning displayed
- **Critical:** 20.0V (0%) - Robot stops movement

### Battery Display
- Visual battery icon with animated fill
- Color-coded: Green (>50%), Yellow (20-50%), Red (<20%)
- Percentage display at top of battery
- Status text overlaid inside battery
- Real-time updates every 5 seconds

## Historical Data & Time Travel

### Features
- Date selector for browsing historical data
- Timeline scrubber for frame-by-frame replay
- Live mode vs. Historical mode toggle
- Previous/Next day navigation
- Data point counter and timestamps

### Usage
1. Select robot from dropdown
2. Choose date with date picker
3. Click "LOAD" to fetch historical data
4. Drag timeline handle to scrub through time
5. Click "LIVE" to return to real-time mode

## Deployment

### Production Deployment with Gunicorn

The robot client supports deployment with Gunicorn for production use:

```bash
cd client
gunicorn -c gunicorn.conf.py wsgi:control_app
```

### Systemd Service (Linux)
Create a systemd service for automatic startup:

```bash
cd client/systemd
./install.sh robot1
```

See `client/systemd/README.md` for detailed instructions.

### Docker Deployment (Future)
Docker support is planned for containerized deployment.

## Development

### Project Structure
```
sitara_app/
├── app.py                      # Main Flask application
├── init_db.py                  # Database initialization
├── seed_data.py                # Sample data generator
├── requirements.txt            # Python dependencies
├── VERSION_MANAGEMENT_GUIDE.md # Version management docs
├── BATTERY_DISPLAY_UPDATE.md   # Battery display docs
├── README.md                   # This file
│
├── database/                   # SQLite database storage
│   └── sitara.db
│
├── static/                     # Static assets
│   ├── css/
│   │   ├── variables.css      # CSS variables (colors, fonts)
│   │   ├── layout.css         # Layout and structure
│   │   └── components.css     # Component styles
│   ├── js/
│   │   └── main.js           # Main JavaScript logic
│   ├── img/                   # Images
│   └── video/                 # Videos
│
├── templates/                  # Jinja2 templates
│   ├── base.html              # Base template
│   ├── index.html             # Landing page
│   ├── login.html             # Login page
│   ├── dashboard.html         # Main dashboard
│   ├── footer.html            # Footer component
│   ├── terms.html             # Terms of service
│   ├── privacy.html           # Privacy policy
│   └── ethics.html            # Ethics statement
│
└── client/                     # Robot client application
    ├── client_app.py          # Main client application
    ├── wsgi.py                # WSGI entry point
    ├── gunicorn.conf.py       # Gunicorn configuration
    ├── requirements.txt       # Client dependencies
    ├── config.env             # Configuration template
    ├── README.md              # Client documentation
    ├── CREDENTIALS.md         # Credential management guide
    ├── GUNICORN_DEPLOYMENT.md # Deployment guide
    └── systemd/               # Systemd service files
        ├── install.sh
        ├── sitara-robot@.service
        └── README.md
```

### Adding New Features

1. **New API Endpoint:**
   - Add route in `app.py`
   - Update database models if needed
   - Document in this README

2. **New Dashboard Widget:**
   - Add HTML in `templates/dashboard.html`
   - Add styles in `static/css/components.css`
   - Add JavaScript in `static/js/main.js`

3. **New Robot Capability:**
   - Update `client/client_app.py`
   - Add constants for configuration
   - Test with control interface

### Testing

#### Manual Testing
1. Start server: `python app.py`
2. Start robot client: `cd client && python client_app.py`
3. Open browser: `http://localhost:5000`
4. Test all features

#### API Testing with cURL
```bash
# Get telemetry
curl http://localhost:5000/api/telemetry?robot_id=1

# Send command
curl -X POST http://localhost:5000/api/robot/command \
  -H "Content-Type: application/json" \
  -d '{"robot_id": 1, "command": "move_up"}'

# Get latest versions
curl http://localhost:5000/api/software/latest_versions
```

## Troubleshooting

### Common Issues

**Issue:** Database not found
- **Solution:** Run `python init_db.py` to create database

**Issue:** Robot not connecting
- **Solution:** Check credentials in `.env` file, verify server is running

**Issue:** Dashboard not updating
- **Solution:** Check browser console for errors, verify robot is sending telemetry

**Issue:** Permission denied on database
- **Solution:** Ensure database directory has write permissions

**Issue:** Version check failing
- **Solution:** Verify robot has internet connection and can reach server

### Debug Mode

Enable Flask debug mode in `app.py`:
```python
if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
```

### Logging

Robot client provides detailed logging:
- `[ROBOT-X]` - Robot operations
- `[CONFIG]` - Configuration loading
- `[CONTROL-UI]` - Control interface
- `✓` - Success operations
- `✗` - Failed operations
- `⚠` - Warnings

## Security Considerations

### Current Implementation
- Basic Flask-Login authentication
- Session-based user management
- Robot-to-user assignment for access control
- Plain text passwords (development only)

### Production Recommendations
1. **Hash passwords** using bcrypt or Argon2, with proper salts
2. **Use HTTPS** with valid SSL certificates
3. **Implement CSRF protection**
4. **Add rate limiting** on API endpoints
5. **Use environment variables** for all secrets
6. **Enable database backups**
7. **Implement proper logging and monitoring**
8. **Use reverse proxy** (nginx) in front of Flask
9. **Implement API key authentication** for robot clients
10. **Regular security audits**

## Performance Optimization

### Database
- Indexed timestamp columns for fast queries
- Periodic cleanup of old telemetry data
- Connection pooling for concurrent requests

### Frontend
- Incremental path history loading
- Debounced timeline scrubbing
- Efficient DOM updates
- Chart data decimation for large datasets

### Network
- Change detection to minimize telemetry traffic
- Compressed JSON responses
- Efficient polling intervals

## Future Enhancements

### Possible Future Features
- [ ] Multi-robot simultaneous view
- [ ] Advanced analytics and reporting
- [ ] Machine learning for anomaly detection
- [ ] Mobile app for remote monitoring
- [ ] Video streaming from robot cameras
- [ ] Voice command integration
- [ ] Automated patrol routes
- [ ] Fleet coordination algorithms
- [ ] Cloud deployment support
- [ ] Real-time notifications/alerts
- [ ] Advanced user roles and permissions
- [ ] API rate limiting
- [ ] 3D visualization

## License

This project is licensed under MIT license.

## Acknowledgments

- Chart.js for data visualization
- Bootstrap for UI framework
- Flask community for excellent documentation
- All contributors and testers

