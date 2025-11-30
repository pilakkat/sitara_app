# SITARA Client-Server Architecture

## Overview

The SITARA system consists of two main components:

1. **Server Application** (`app.py`) - Flask-based web dashboard
2. **Client Application** (`client/client_app.py`) - Robot simulator

## Architecture Diagram

```
┌─────────────────────────────────────────────────────────────┐
│                     SITARA SERVER (Flask)                    │
│                    http://127.0.0.1:5001                     │
├─────────────────────────────────────────────────────────────┤
│                                                               │
│  Web Dashboard              API Endpoints                    │
│  ┌──────────────┐          ┌────────────────────────┐       │
│  │ Login Page   │          │ /api/robot/telemetry   │       │
│  │ Dashboard    │          │ /api/robot/commands    │       │
│  │ - Map View   │          │ /api/robot/command     │       │
│  │ - Charts     │          │ /api/telemetry         │       │
│  │ - Logs       │          │ /api/path_history      │       │
│  │ - Controls   │          └────────────────────────┘       │
│  └──────────────┘                                            │
│         │                           ▲                        │
│         │ User Interaction          │ HTTP Requests          │
│         ▼                           │                        │
│  ┌─────────────────────────────────┴──────────┐            │
│  │           Database (SQLite)                 │            │
│  │  - Users                                    │            │
│  │  - Robots                                   │            │
│  │  - TelemetryLog (battery, temp, status)    │            │
│  │  - PathLog (x, y, orientation)             │            │
│  └────────────────────────────────────────────┘            │
└─────────────────────────────────────────────────────────────┘
                           ▲            │
                           │            │
         Telemetry         │            │  Commands
         (POST)            │            │  (GET)
                           │            ▼
┌──────────────────────────┴────────────────────────────────┐
│              ROBOT CLIENT (Python Script)                  │
│                  client/client_app.py                      │
├────────────────────────────────────────────────────────────┤
│                                                             │
│  Authentication Thread     Command Thread                  │
│  ┌──────────────┐         ┌──────────────┐               │
│  │ Login Once   │         │ Check Every  │               │
│  │ Get Session  │         │ 3 seconds    │               │
│  └──────────────┘         └──────────────┘               │
│                                                             │
│  Telemetry Thread          Robot State                     │
│  ┌──────────────┐         ┌──────────────┐               │
│  │ Send Every   │         │ Position     │               │
│  │ 2 seconds    │◄────────│ Battery      │               │
│  └──────────────┘         │ Temperature  │               │
│                            │ Status       │               │
│                            └──────────────┘               │
└────────────────────────────────────────────────────────────┘
```

## Communication Flow

### 1. Startup & Authentication

```
Client                          Server
  │                               │
  ├──POST /login─────────────────►│
  │  (username, password)         │
  │                               │
  │◄─────Session Cookie───────────┤
  │                               │
  └──Authenticated──────────────► │
```

### 2. Telemetry Upload (Every 2 seconds)

```
Client                                    Server
  │                                         │
  ├──POST /api/robot/telemetry────────────►│
  │  {                                      │
  │    robot_id: 1,                         │
  │    battery_voltage: 24.5,               │
  │    temperature: 45.0,                   │
  │    motor_load: 65,                      │
  │    status: "MOVING",                    │
  │    x: 52.3,                             │
  │    y: 48.7,                             │
  │    orientation: 45.2                    │
  │  }                                      │
  │                                         │
  │                                         ├──Save to DB─┐
  │                                         │              │
  │◄────{status: "success"}─────────────────┤              │
  │                                         │◄─────────────┘
```

### 3. Command Retrieval (Every 3 seconds)

```
Client                                    Server
  │                                         │
  ├──GET /api/robot/commands?robot_id=1───►│
  │                                         │
  │                                         ├──Check Queue─┐
  │                                         │              │
  │◄────[{command: "move_forward"}]────────┤◄─────────────┘
  │                                         │
  ├──Execute Command─────────────────┐     │
  │                                   │     │
  │◄──Status Update───────────────────┘     │
```

### 4. Dashboard Control Flow

```
User                Dashboard              Server              Client
  │                     │                    │                    │
  ├──Click "FWD"───────►│                    │                    │
  │                     │                    │                    │
  │                     ├──POST /api/robot/──►│                   │
  │                     │   command           │                   │
  │                     │   {command: "move_  │                   │
  │                     │    forward"}        │                   │
  │                     │                     │                   │
  │                     │                     ├──Queue Command─┐  │
  │                     │                     │                │  │
  │                     │◄────ACK─────────────┤◄───────────────┘  │
  │                     │                     │                   │
  │◄──"Command Sent"────┤                     │                   │
  │                     │                     │                   │
  │                     │                     │◄──Poll Commands───┤
  │                     │                     │                   │
  │                     │                     ├──Send Command────►│
  │                     │                     │                   │
  │                     │                     │                   ├──Execute─┐
  │                     │                     │                   │          │
  │                     │                     │◄──Telemetry Update┤◄─────────┘
  │                     │◄──Live Data─────────┤   (status changed)│
  │                     │                     │                   │
  │◄──Map Updates───────┤                     │                   │
```

## API Endpoints

### Server Endpoints (for Clients)

| Endpoint | Method | Auth | Description |
|----------|--------|------|-------------|
| `/login` | POST | No | Authenticate and get session |
| `/api/robot/telemetry` | POST | Yes | Upload telemetry data |
| `/api/robot/commands` | GET | Yes | Retrieve pending commands |
| `/api/robot/command` | POST | Yes | Queue command for robot |

### Dashboard Endpoints (for Web UI)

| Endpoint | Method | Auth | Description |
|----------|--------|------|-------------|
| `/` | GET | No | Landing page |
| `/dashboard` | GET | Yes | Main control interface |
| `/api/telemetry` | GET | Yes | Latest robot status |
| `/api/path_history` | GET | Yes | Movement history |
| `/api/telemetry_history` | GET | Yes | Health logs |
| `/api/health_history` | GET | Yes | Chart data |

## Data Models

### Robot
```python
{
    id: Integer,
    serial_number: String,  # e.g., "S4-0001"
    model_type: String,     # "32DOF-HUMANOID"
    assigned_to: Integer    # User ID
}
```

### TelemetryLog
```python
{
    id: Integer,
    robot_id: Integer,
    timestamp: DateTime,
    battery_voltage: Float,  # 22.0 - 25.2V
    temperature: Float,      # 35 - 85°C
    motor_load: Integer,     # 0 - 100%
    status: String,          # IDLE, MOVING, SCANNING, BATTERY LOW
    cycle_count: Integer
}
```

### PathLog
```python
{
    id: Integer,
    robot_id: Integer,
    timestamp: DateTime,
    x: Float,           # 0 - 100
    y: Float,           # 0 - 100
    orientation: Float  # 0 - 360°
}
```

## Multi-Client Support

The system supports multiple robot clients connecting simultaneously:

```
┌─────────────────┐
│  Client Robot 1 │──┐
│  (ID: 1)        │  │
└─────────────────┘  │
                     │
┌─────────────────┐  │    ┌──────────────┐
│  Client Robot 2 │──┼───►│  Server      │
│  (ID: 2)        │  │    │  Database    │
└─────────────────┘  │    └──────────────┘
                     │
┌─────────────────┐  │
│  Client Robot 3 │──┘
│  (ID: 3)        │
└─────────────────┘
```

Each client:
- Has a unique `robot_id`
- Maintains independent state
- Receives only its own commands
- Can be controlled by different users

## Running Multiple Clients

### Terminal 1 - Server
```bash
python app.py
```

### Terminal 2 - Robot 1
```bash
cd client
python client_app.py 1
```

### Terminal 3 - Robot 2
```bash
cd client
python client_app.py 2 operator operator123
```

### Terminal 4 - Robot 3
```bash
cd client
python client_app.py 3
```

## Security Considerations

### Current Implementation (Development)
- Session-based authentication
- In-memory command queue
- Plain text passwords (demo only)

### Production Recommendations
1. Use HTTPS for all connections
2. Hash passwords with bcrypt
3. Use Redis for command queue
4. Add API rate limiting
5. Implement token-based auth (JWT)
6. Add robot authentication (API keys)
7. Validate all inputs
8. Add CORS protection

## File Structure

```
sitara_app/
│
├── app.py                    # Main server application
├── requirements.txt          # Server dependencies
├── init_db.py               # Database initialization
├── seed_data.py             # Test data generator
│
├── client/                  # Robot client (isolated)
│   ├── client_app.py        # Client application
│   ├── requirements.txt     # Client dependencies
│   ├── config.env           # Configuration file
│   ├── README.md            # Client documentation
│   └── start_client.bat     # Windows launcher
│
├── database/
│   └── sitara.db            # SQLite database
│
├── static/
│   ├── css/                 # Stylesheets
│   ├── js/
│   │   └── main.js          # Dashboard logic
│   └── img/
│
└── templates/
    ├── base.html
    ├── dashboard.html       # Main UI
    └── login.html
```

## Troubleshooting

### Client Can't Connect
1. Verify server is running
2. Check SERVER_URL in client config
3. Ensure firewall allows connections
4. Test with: `curl http://127.0.0.1:5001`

### Authentication Fails
1. Check username/password
2. Verify user exists: `SELECT * FROM user;`
3. Check server logs

### Commands Not Received
1. Verify client is authenticated
2. Check robot_id matches
3. Look for errors in server logs
4. Test endpoint: `/api/robot/commands?robot_id=1`

### No Telemetry on Dashboard
1. Check if client is sending data
2. Verify robot_id in database
3. Check browser console for errors
4. Test endpoint: `/api/telemetry`
