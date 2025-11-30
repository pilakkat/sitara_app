# SITARA Robot Client

This is a standalone client application that simulates a robot connecting to the SITARA server.

## Features

- **Authentication**: Logs in to the server using username/password
- **Telemetry Transmission**: Sends real-time position, battery, temperature, and status data
- **Command Reception**: Receives and executes commands from the server dashboard
- **Autonomous Movement**: Simulates realistic robot behavior and movement patterns
- **Multi-Client Support**: Multiple robot clients can connect simultaneously

## Installation

1. Install required dependencies:
```bash
pip install -r requirements.txt
```

Or manually:
```bash
pip install requests python-dotenv
```

## Configuration

### Quick Setup

1. **Create your personal `.env` file** (not tracked by git):
```bash
# Copy the example file
copy .env.example .env

# Edit .env and add your credentials
```

2. **Update `.env` with your credentials**:
```properties
SERVER_URL=http://127.0.0.1:5001
ROBOT_USERNAME=your-operator-username
ROBOT_PASSWORD=your-operator-password
ROBOT_ID=1
```

**Important:** 
- The `.env` file is **ignored by git** to protect your credentials
- Never commit `.env` file to version control
- Variable names use `ROBOT_USERNAME` and `ROBOT_PASSWORD` to avoid conflicts with Windows system environment variables
- Each robot client should authenticate as an **operator** user, not as `admin`
- Contact your system administrator for operator credentials

### Configuration Priority

The client loads configuration in this order:
1. **`.env`** - Your personal credentials (highest priority, git-ignored)
2. **`config.env`** - Default template with placeholders (tracked by git)
3. **Command line arguments** - Override any setting (highest priority)

### Running Multiple Robots

To run multiple robot clients simultaneously, create separate `.env` files or use command line arguments:

**Option 1: Separate directories**
```bash
# Robot 1
cd client
python client_app.py

# Robot 2 (in another terminal)
cd client2
python client_app.py
```

**Option 2: Command line override**
```bash
# Robot 1
python client_app.py 1 operator1 password1

# Robot 2
python client_app.py 2 operator2 password2

# Robot 3
python client_app.py 3 operator3 password3
```

You can override these settings via command line arguments.

## Usage

### Basic Usage (Uses .env credentials)
```bash
python client_app.py
```

### Specify Robot ID
```bash
python client_app.py 2
```

### Specify Robot ID and Credentials (Command Line Override)
```bash
python client_app.py 1 <username> <password>
```

### Multiple Robots (Each as different operators or same)
Run multiple instances in separate terminals:
```bash
# Terminal 1 - Robot 1 as operator
python client_app.py 1

# Terminal 2 - Robot 2 as operator
python client_app.py 2

# Terminal 3 - Robot 3 as different user
python client_app.py 3 <username> <password>
```

## Commands

The client responds to the following commands from the dashboard:

- `move_forward` - Robot moves forward
- `stop` / `halt` - Robot stops all movement
- `scan_area` - Robot rotates in place (scanning mode)

## Client Behavior

### Status States
- **IDLE** - Robot is stationary, battery recovering, cooling down
- **MOVING** - Robot is moving forward, consuming battery
- **SCANNING** - Robot is rotating in place
- **BATTERY LOW** - Battery voltage below 23V, automatic stop

### Telemetry Updates
- Position (X, Y, Orientation)
- Battery Voltage (22.0V - 25.2V)
- CPU Temperature (35°C - 85°C)
- Motor Load (0-100%)
- Status and Cycle Count

### Update Intervals
- Telemetry: Every 2 seconds
- Command Check: Every 3 seconds

## Architecture

```
┌─────────────────┐         ┌──────────────────┐
│  Robot Client   │◄────────┤  SITARA Server   │
│   (This App)    │         │   (Flask App)    │
│                 │         │                  │
│  - Auth Login   │────────►│  /login          │
│  - Send Data    │────────►│  /api/robot/     │
│  - Get Commands │◄────────│     telemetry    │
│  - Execute      │         │     commands     │
└─────────────────┘         └──────────────────┘
```

## Troubleshooting

### Connection Failed
- Ensure the SITARA server is running on the correct port
- Check the SERVER_URL in the configuration
- Verify network connectivity

### Authentication Failed
- Verify username and password are correct
- Check if the user exists in the server database

### Commands Not Executing
- Check server logs for errors
- Ensure robot is authenticated
- Verify command API endpoint is available

## Development

To modify robot behavior, edit these methods in `RobotClient`:

- `update_robot_state()` - Movement and physics simulation
- `execute_command()` - Command handling logic
- `send_telemetry()` - Data transmission format

## Notes

- This is a simulation client for testing and demonstration
- In production, replace with actual robot firmware/software
- Command queue is stored in server memory (consider Redis for production)
- Multiple clients can connect using different Robot IDs
- Each client maintains independent state and position
