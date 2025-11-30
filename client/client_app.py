"""
SITARA Robot Client Application
Simulates a robot that connects to the server, sends telemetry, and receives commands.
Includes a minimal web interface for manual control.
"""

import requests
import time
import json
import random
import math
import os
from datetime import datetime, timezone
from threading import Thread, Event
from dotenv import load_dotenv
from flask import Flask, render_template_string, render_template, request, jsonify
import sys

# Import client database manager
from client_database import ClientDatabase

# ============================================================================
# CONFIGURATION CONSTANTS
# ============================================================================

# Battery Configuration (24V Li-ion 6S system)
BATTERY_MAX_VOLTAGE = 25.2  # Fully charged voltage
BATTERY_MIN_VOLTAGE = 20.0  # Critical/empty voltage
BATTERY_NOMINAL_VOLTAGE = 24.5  # Normal operating voltage
BATTERY_LOW_THRESHOLD = 22.65  # Warning threshold (~38%)
BATTERY_CRITICAL_THRESHOLD = 20.0  # Critical threshold - stop movement

# Temperature Configuration (Celsius)
TEMP_MIN = 35  # Minimum temperature when idle
TEMP_MAX = 85  # Maximum safe temperature
TEMP_NORMAL = 45  # Normal operating temperature
TEMP_COOLDOWN_RATE = 0.2  # Temperature decrease rate when idle
TEMP_INCREASE_MOVING = 0.1  # Temperature increase when moving
TEMP_INCREASE_SCANNING = 0.05  # Temperature increase when scanning

# Movement Configuration
MOVEMENT_SPEED = 1.0  # Units per update cycle
MOVEMENT_BATTERY_DRAIN = 0.001  # Battery drain per movement cycle
STANDBY_BATTERY_RECOVERY = 0.002  # Battery recovery when idle
COLLISION_BUFFER = 2  # Safety buffer around obstacles (%)

# Position Boundaries (% of map)
MAP_SAFE_MIN = 5  # Minimum safe position
MAP_SAFE_MAX = 95  # Maximum safe position

# Telemetry Timing
TELEMETRY_INTERVAL = 5  # Seconds between telemetry updates
COMMAND_CHECK_INTERVAL = 3  # Seconds between command checks

# Motor Load
MOTOR_LOAD_MOVING = 65  # Motor load % when moving
MOTOR_LOAD_SCANNING = 30  # Motor load % when scanning
MOTOR_LOAD_STANDBY = 0  # Motor load % when idle

# Robot Status Codes
STATUS_STANDBY = "STANDBY"
STATUS_MOVING = "MOVING"
STATUS_SCANNING = "SCANNING"
STATUS_CHARGING = "CHARGING"
STATUS_FAULT = "FAULT"
STATUS_OFFLINE = "OFFLINE"
STATUS_BOOTING = "BOOTING"
STATUS_BATTERY_LOW_SUFFIX = " | BAT LOW"

# Software Version Configuration
VERSION_RCPCU = '2.3.1'  # Robot Central Processing & Control Unit
VERSION_RCSPM = '1.8.5'  # Robot Control System & Power Management
VERSION_RCMMC = '3.1.2'  # Robot Control Motion & Motor Controller
VERSION_RCPMU = '1.5.9'  # Robot Control Power Management Unit

# Network Timeouts
NETWORK_TIMEOUT_DEFAULT = 5  # Default timeout for API calls (seconds)
NETWORK_TIMEOUT_EXTENDED = 10  # Extended timeout for version checks (seconds)

# ============================================================================
# OBSTACLE DEFINITIONS
# ============================================================================

# Define obstacle boundaries (x, y, width, height in %)
OBSTACLES = [
    # Walls (5% thick)
    {'x': 0, 'y': 0, 'width': 100, 'height': 5, 'name': 'North Wall'},
    {'x': 0, 'y': 95, 'width': 100, 'height': 5, 'name': 'South Wall'},
    {'x': 0, 'y': 0, 'width': 5, 'height': 100, 'name': 'West Wall'},
    {'x': 95, 'y': 0, 'width': 5, 'height': 100, 'name': 'East Wall'},
    
    # Furniture
    {'x': 15, 'y': 35, 'width': 25, 'height': 30, 'name': 'Conference Table'},
    {'x': 70, 'y': 10, 'width': 20, 'height': 15, 'name': 'Desk'},
    {'x': 75, 'y': 27, 'width': 8, 'height': 8, 'name': 'Chair'},
    {'x': 70, 'y': 75, 'width': 20, 'height': 18, 'name': 'Storage Cabinet'},
    {'x': 55, 'y': 48, 'width': 8, 'height': 8, 'name': 'Pillar'}
]

def check_collision(x, y, obstacles, buffer=COLLISION_BUFFER):
    """Check if position collides with any obstacle"""
    for obstacle in obstacles:
        if (x >= (obstacle['x'] - buffer) and 
            x <= (obstacle['x'] + obstacle['width'] + buffer) and
            y >= (obstacle['y'] - buffer) and 
            y <= (obstacle['y'] + obstacle['height'] + buffer)):
            print(f"[COLLISION-DEBUG] Position ({x:.1f}, {y:.1f}) collides with {obstacle['name']}")
            return True
    return False

def is_valid_position(x, y, obstacles):
    """Check if position is valid (within bounds and no collision)"""
    # Keep robot within safe area (away from edges)
    if x < MAP_SAFE_MIN or x > MAP_SAFE_MAX or y < MAP_SAFE_MIN or y > MAP_SAFE_MAX:
        return False
    # Check obstacle collision
    return not check_collision(x, y, obstacles)

def find_nearest_safe_position(x, y, obstacles):
    """Find the nearest safe position to the given coordinates
    
    This is used when the robot is initialized inside an obstacle (e.g., demo system).
    Searches outward in a spiral pattern to find the nearest valid position.
    """
    # If already valid, return as-is
    if is_valid_position(x, y, obstacles):
        return x, y
    
    print(f"[COLLISION] Position ({x:.1f}, {y:.1f}) is inside obstacle, finding safe position...")
    
    # Try positions in expanding circles around the current position
    max_search_radius = 50  # Maximum distance to search
    step = 1  # Search step size
    
    for radius in range(1, max_search_radius, step):
        # Check positions in a circle around the current point
        for angle in range(0, 360, 15):  # Check every 15 degrees
            rad = angle * (math.pi / 180)
            test_x = x + radius * math.cos(rad)
            test_y = y + radius * math.sin(rad)
            
            if is_valid_position(test_x, test_y, obstacles):
                print(f"[COLLISION] Found safe position at ({test_x:.1f}, {test_y:.1f}), distance: {radius:.1f}")
                return test_x, test_y
    
    # Fallback to center of map if nothing found
    center_x, center_y = 50.0, 50.0
    print(f"[COLLISION] No safe position found nearby, using map center ({center_x}, {center_y})")
    return center_x, center_y

# ============================================================================
# ENVIRONMENT CONFIGURATION (Module-level initialization for gunicorn safety)
# ============================================================================

# Get the directory where this script is located (for relative path resolution)
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))

# Load environment variables with flexible priority:
# 1. System environment (from systemd EnvironmentFile or shell)
# 2. .env file (personal credentials, optional)
# 3. config.env (defaults/template, optional)
# 
# For systemd deployment: Use EnvironmentFile instead of .env/config.env
# For development: Use .env or config.env for convenience
env_file = os.path.join(SCRIPT_DIR, '.env')
config_file = os.path.join(SCRIPT_DIR, 'config.env')

if os.path.exists(env_file):
    print(f"[CONFIG] Loading credentials from {env_file}")
    load_dotenv(env_file, override=False)  # Don't override existing env vars
elif os.path.exists(config_file):
    print(f"[CONFIG] Loading defaults from {config_file}")
    load_dotenv(config_file, override=False)
else:
    print(f"[CONFIG] No .env or config.env found, using system environment only")

# Load configuration from environment (safe for gunicorn & systemd)
# Note: Using ROBOT_USERNAME/ROBOT_PASSWORD to avoid conflicts with Windows USERNAME env var
SERVER_URL = os.getenv('SERVER_URL', 'http://127.0.0.1:5001')
USERNAME = os.getenv('ROBOT_USERNAME')
PASSWORD = os.getenv('ROBOT_PASSWORD')
ROBOT_ID = int(os.getenv('ROBOT_ID', '1'))
UI_PORT = int(os.getenv('CLIENT_UI_PORT', '5001'))

# Try to load credentials from database (overrides .env if available)
# This ensures that if a user successfully logged in with a new password via retry,
# the database password takes precedence over the .env file
try:
    from client_database import ClientDatabase
    db = ClientDatabase()
    if os.path.exists(db.db_path):
        # Get user from database for this robot
        robot_data = db.get_robot(ROBOT_ID)
        if robot_data and robot_data['assigned_user_id']:
            # Get the user assigned to this robot
            with db.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('SELECT username, password FROM user WHERE id = ?', 
                             (robot_data['assigned_user_id'],))
                user = cursor.fetchone()
                if user:
                    db_username = user['username']
                    db_password = user['password']
                    # Override with database credentials
                    if db_username and db_password:
                        USERNAME = db_username
                        PASSWORD = db_password
                        print(f"[CONFIG] Loaded credentials from database (overriding .env)")
except Exception as e:
    # If database doesn't exist or has errors, fall back to .env values
    print(f"[CONFIG] Could not load from database (using .env): {e}")
    pass

# Validate configuration
if not USERNAME or not PASSWORD:
    print("\n[ERROR] Missing credentials!")
    print("Please set ROBOT_USERNAME and ROBOT_PASSWORD environment variables")
    print("or create a .env file with these values")
    print("See .env.example for template")
    # Don't exit immediately - allow import to succeed for gunicorn
    # but log the error clearly
    USERNAME = USERNAME or 'MISSING_USERNAME'
    PASSWORD = PASSWORD or 'MISSING_PASSWORD'

if USERNAME.startswith('<') or USERNAME.startswith('your-'):
    print("\n[WARNING] Username appears to be a placeholder!")
    print("Please update .env with actual credentials")

print(f"[CONFIG] Server: {SERVER_URL}")
print(f"[CONFIG] Robot ID: {ROBOT_ID}")
print(f"[CONFIG] User: {USERNAME}")
print(f"[CONFIG] Control UI Port: {UI_PORT}")

# Flask app for control interface
control_app = Flask(__name__)

# Robot client instance (initialized at module level for gunicorn compatibility)
robot_client = None

class RobotClient:
    def __init__(self, server_url, username, password, robot_id=1):
        self.server_url = server_url.rstrip('/')
        self.username = username
        self.password = password
        self.robot_id = robot_id
        self.session = requests.Session()
        self.running = False
        self.stop_event = Event()
        
        # Initialize database
        self.db = ClientDatabase()
        
        # Robot-specific obstacles (fetched from server)
        self.obstacles = []
        
        # Robot state
        self.position = {'x': 30.0, 'y': 20.0, 'orientation': 0.0}  # Start in open area
        self.battery_voltage = BATTERY_NOMINAL_VOLTAGE
        self.temperature = TEMP_NORMAL
        self.motor_load = MOTOR_LOAD_STANDBY
        self.status = STATUS_STANDBY
        self.cycle_count = 0
        self.is_powered_on = True  # Track power state
        
        # Load software versions from database (fallback to constants)
        db_versions = self.db.get_robot_versions(robot_id)
        self.versions = db_versions if db_versions else {
            'RCPCU': VERSION_RCPCU,
            'RCSPM': VERSION_RCSPM,
            'RCMMC': VERSION_RCMMC,
            'RCPMU': VERSION_RCPMU
        }
        self.last_version_check = None
        
        # Track previous state for change detection
        self.last_telemetry_state = None
        
        # Movement parameters
        self.speed = MOVEMENT_SPEED
        self.current_command = None
        
        # Authentication state
        self.authenticated = False
        self.last_session_check = None
        self.session_check_interval = 60  # Check session every 60 seconds
        
        print(f"[ROBOT-{self.robot_id}] Initializing client...")
        print(f"[ROBOT-{self.robot_id}] Loaded versions from database: {self.versions}")
    
    def login(self):
        """Authenticate with the server"""
        try:
            login_url = f"{self.server_url}/login"
            response = self.session.post(
                login_url,
                data={
                    'username': self.username,
                    'password': self.password
                },
                allow_redirects=False
            )
            
            # Successful login returns a 302 redirect to dashboard
            # Failed login returns 200 with login page HTML
            if response.status_code == 302:
                redirect_location = response.headers.get('Location', '')
                if 'dashboard' in redirect_location or redirect_location.endswith('/dashboard'):
                    print(f"[ROBOT-{self.robot_id}] ✓ Authenticated as {self.username}")
                    self.authenticated = True
                    return True
                else:
                    print(f"[ROBOT-{self.robot_id}] ✗ Authentication failed: Unexpected redirect to {redirect_location}")
                    self.authenticated = False
                    return False
            elif response.status_code == 200:
                # Status 200 means we got the login page back = authentication failed
                print(f"[ROBOT-{self.robot_id}] ✗ Authentication failed: Invalid credentials")
                self.authenticated = False
                return False
            else:
                print(f"[ROBOT-{self.robot_id}] ✗ Authentication failed: HTTP {response.status_code}")
                self.authenticated = False
                return False
        except Exception as e:
            print(f"[ROBOT-{self.robot_id}] ✗ Login error: {e}")
            self.authenticated = False
            return False
    
    def retry_authentication(self, new_password):
        """Retry authentication with a new password"""
        old_password = self.password
        self.password = new_password
        login_success = self.login()
        
        # If login is successful, update password in database
        if login_success and self.db:
            try:
                updated = self.db.update_user_password(self.username, new_password)
                if updated:
                    print(f"[ROBOT-{self.robot_id}] ✓ Password updated in database for user: {self.username}")
                else:
                    print(f"[ROBOT-{self.robot_id}] ⚠ Password update in database failed for user: {self.username}")
            except Exception as e:
                print(f"[ROBOT-{self.robot_id}] ⚠ Error updating password in database: {e}")
        
        return login_success
    
    def check_session_validity(self):
        """Check if the server session is still valid"""
        try:
            response = self.session.get(
                f"{self.server_url}/api/session/check",
                timeout=NETWORK_TIMEOUT_DEFAULT
            )
            
            if response.status_code == 200:
                # Session is valid
                self.last_session_check = datetime.now(timezone.utc)
                return True
            elif response.status_code == 401:
                # Session expired
                print(f"[ROBOT-{self.robot_id}] ⚠️ Session expired after 30 minutes of inactivity")
                self.authenticated = False
                return False
            else:
                # Other error, assume session invalid
                print(f"[ROBOT-{self.robot_id}] ⚠️ Session check failed with status {response.status_code}")
                self.authenticated = False
                return False
        except Exception as e:
            print(f"[ROBOT-{self.robot_id}] ✗ Session check error: {e}")
            # Don't mark as unauthenticated on network errors
            return None  # Return None to indicate check failed (not necessarily expired)
    
    def should_check_session(self):
        """Determine if it's time to check session validity"""
        if not self.last_session_check:
            return True
        
        now = datetime.now(timezone.utc)
        time_since_last_check = (now - self.last_session_check).total_seconds()
        
        return time_since_last_check >= self.session_check_interval
    
    def check_software_updates(self):
        """Check for software updates from server"""
        try:
            response = self.session.get(
                f"{self.server_url}/api/software/latest_versions",
                timeout=NETWORK_TIMEOUT_EXTENDED
            )
            
            if response.status_code == 200:
                latest_versions = response.json()
                self.last_version_check = datetime.now(timezone.utc)
                
                # Update database with available versions
                release_date = latest_versions.get('release_date', '')
                release_notes_data = latest_versions.get('release_notes', {})
                
                updates_available = False
                for controller in ['RCPCU', 'RCSPM', 'RCMMC', 'RCPMU']:
                    if controller in latest_versions:
                        available_version = latest_versions[controller]
                        release_notes = release_notes_data.get(controller, '')
                        
                        # Save to database with robot_id
                        self.db.update_available_version(
                            self.robot_id,
                            controller, 
                            available_version, 
                            release_date, 
                            release_notes
                        )
                        
                        if self.versions[controller] != available_version:
                            updates_available = True
                
                # Update last check timestamp in robot table
                self.db.update_last_version_check(self.robot_id)
                
                print(f"[ROBOT-{self.robot_id}] ✓ Version check completed")
                print(f"[ROBOT-{self.robot_id}]   Current versions:")
                for controller, version in self.versions.items():
                    latest = latest_versions.get(controller, 'unknown')
                    status = "✓ UP TO DATE" if version == latest else f"⚠ UPDATE AVAILABLE: {latest}"
                    print(f"[ROBOT-{self.robot_id}]     {controller}: {version} {status}")
                
                if updates_available:
                    print(f"[ROBOT-{self.robot_id}] 🔔 Software updates available! Check the Updates tab.")
                
                # Send current versions to server
                self.send_version_info()
                
                return latest_versions
            else:
                print(f"[ROBOT-{self.robot_id}] ⚠ Version check failed: HTTP {response.status_code}")
                return None
        except Exception as e:
            print(f"[ROBOT-{self.robot_id}] ⚠ Version check error: {e}")
            return None
    
    def send_version_info(self):
        """Send current software versions to server"""
        try:
            version_data = {
                'robot_id': self.robot_id,
                'version_rcpcu': self.versions['RCPCU'],
                'version_rcspm': self.versions['RCSPM'],
                'version_rcmmc': self.versions['RCMMC'],
                'version_rcpmu': self.versions['RCPMU']
            }
            
            response = self.session.post(
                f"{self.server_url}/api/robot/version",
                json=version_data,
                timeout=NETWORK_TIMEOUT_DEFAULT
            )
            
            if response.status_code == 200:
                print(f"[ROBOT-{self.robot_id}] ✓ Version info sent to server")
                return True
            else:
                print(f"[ROBOT-{self.robot_id}] ⚠ Failed to send version info: HTTP {response.status_code}")
                return False
        except Exception as e:
            print(f"[ROBOT-{self.robot_id}] ⚠ Error sending version info: {e}")
            return False
    
    def should_check_versions(self):
        """Determine if it's time to check for updates (daily at midnight)"""
        if not self.last_version_check:
            return True
        
        now = datetime.now(timezone.utc)
        # Check if it's a new day
        if now.date() > self.last_version_check.date():
            # Check if it's midnight hour (00:00 - 00:59)
            if now.hour == 0:
                return True
        
        return False
    
    def fetch_obstacles(self):
        """Fetch robot-specific obstacles from server"""
        try:
            response = self.session.get(
                f"{self.server_url}/api/obstacles",
                params={'robot_id': self.robot_id},
                timeout=NETWORK_TIMEOUT_DEFAULT
            )
            
            if response.status_code == 200:
                obstacles_data = response.json()
                self.obstacles = obstacles_data
                print(f"[ROBOT-{self.robot_id}] ✓ Loaded {len(self.obstacles)} obstacles from server")
                for obs in self.obstacles:
                    print(f"[ROBOT-{self.robot_id}]   - {obs['name']}: ({obs['x']}, {obs['y']}) {obs['width']}x{obs['height']}")
                return True
            else:
                print(f"[ROBOT-{self.robot_id}] ⚠ Failed to fetch obstacles: HTTP {response.status_code}")
                # Fall back to global OBSTACLES if server fetch fails
                self.obstacles = OBSTACLES
                print(f"[ROBOT-{self.robot_id}] ⚠ Using default global obstacles as fallback")
                return False
        except Exception as e:
            print(f"[ROBOT-{self.robot_id}] ⚠ Error fetching obstacles: {e}")
            # Fall back to global OBSTACLES
            self.obstacles = OBSTACLES
            print(f"[ROBOT-{self.robot_id}] ⚠ Using default global obstacles as fallback")
            return False
    
    def fetch_last_position(self):
        """Fetch the last known position from the server"""
        try:
            response = self.session.get(
                f"{self.server_url}/api/telemetry",
                params={'robot_id': self.robot_id},
                timeout=NETWORK_TIMEOUT_DEFAULT
            )
            
            if response.status_code == 200:
                data = response.json()
                if data and 'pos_x' in data and 'pos_y' in data:
                    self.position['x'] = data.get('pos_x', 50.0)
                    self.position['y'] = data.get('pos_y', 50.0)
                    self.position['orientation'] = data.get('orientation', 0.0)
                    print(f"[ROBOT-{self.robot_id}] ✓ Restored last position: ({self.position['x']:.1f}, {self.position['y']:.1f}), orientation: {self.position['orientation']:.1f}°")
                    
                    # Safety check: If position is inside an obstacle, move to nearest safe position
                    if not is_valid_position(self.position['x'], self.position['y'], self.obstacles):
                        safe_x, safe_y = find_nearest_safe_position(self.position['x'], self.position['y'], self.obstacles)
                        self.position['x'] = safe_x
                        self.position['y'] = safe_y
                        print(f"[ROBOT-{self.robot_id}] ⚠ Corrected to safe position: ({safe_x:.1f}, {safe_y:.1f})")
                    
                    # Also restore other state if available
                    if 'battery' in data:
                        self.battery_voltage = data.get('battery', 24.5)
                    if 'cpu_temp' in data:
                        self.temperature = data.get('cpu_temp', 45.0)
                    if 'status' in data and data['status'] != 'UNKNOWN':
                        self.status = data.get('status', 'STANDBY')
                    if 'cycles' in data:
                        self.cycle_count = data.get('cycles', 0)
                    
                    return True
                else:
                    print(f"[ROBOT-{self.robot_id}] ℹ No previous position found, using default (50.0, 50.0)")
                    return True
            else:
                print(f"[ROBOT-{self.robot_id}] ⚠ Could not fetch last position (HTTP {response.status_code}), using default")
                return True  # Continue with defaults
        except Exception as e:
            print(f"[ROBOT-{self.robot_id}] ⚠ Error fetching last position: {e}, using default")
            return True  # Continue with defaults
    
    def send_telemetry(self):
        """Send current telemetry data to server (only if data has changed)"""
        # Don't send telemetry if powered off
        if not self.is_powered_on:
            return True
            
        try:
            # Generate timestamp on client side for accurate time tracking
            timestamp = datetime.now(timezone.utc).isoformat()
            
            # Get status with battery warning appended if needed
            status_to_send = self.get_status_with_battery_warning()
            
            # Current state (excluding timestamp for comparison)
            current_state = {
                'robot_id': self.robot_id,
                'battery_voltage': round(self.battery_voltage, 2),
                'temperature': round(self.temperature, 1),
                'motor_load': self.motor_load,
                'status': status_to_send,
                'cycle_count': self.cycle_count,
                'x': round(self.position['x'], 2),
                'y': round(self.position['y'], 2),
                'orientation': round(self.position['orientation'], 2)
            }
            
            # Check if state has changed (excluding timestamp)
            if self.last_telemetry_state == current_state:
                # No change, skip sending
                return True
            
            # State has changed, prepare telemetry data with timestamp
            telemetry_data = current_state.copy()
            telemetry_data['timestamp'] = timestamp
            
            response = self.session.post(
                f"{self.server_url}/api/robot/telemetry",
                json=telemetry_data,
                timeout=NETWORK_TIMEOUT_DEFAULT
            )
            
            if response.status_code == 200:
                # Update last sent state
                self.last_telemetry_state = current_state
                print(f"[ROBOT-{self.robot_id}] → Telemetry sent | Status: {status_to_send} | Pos: ({self.position['x']:.1f}, {self.position['y']:.1f}) | Battery: {self.battery_voltage:.2f}V")
                return True
            else:
                print(f"[ROBOT-{self.robot_id}] ✗ Telemetry failed: {response.status_code}")
                return False
        except Exception as e:
            print(f"[ROBOT-{self.robot_id}] ✗ Telemetry error: {e}")
            return False
    
    def send_telemetry_immediate(self):
        """Force send telemetry immediately regardless of change detection"""
        try:
            timestamp = datetime.now(timezone.utc).isoformat()
            
            # Get status with battery warning appended if needed
            status_to_send = self.get_status_with_battery_warning()
            
            current_state = {
                'robot_id': self.robot_id,
                'battery_voltage': round(self.battery_voltage, 2),
                'temperature': round(self.temperature, 1),
                'motor_load': self.motor_load,
                'status': status_to_send,
                'cycle_count': self.cycle_count,
                'x': round(self.position['x'], 2),
                'y': round(self.position['y'], 2),
                'orientation': round(self.position['orientation'], 2)
            }
            
            telemetry_data = current_state.copy()
            telemetry_data['timestamp'] = timestamp
            
            response = self.session.post(
                f"{self.server_url}/api/robot/telemetry",
                json=telemetry_data,
                timeout=NETWORK_TIMEOUT_DEFAULT
            )
            
            if response.status_code == 200:
                self.last_telemetry_state = current_state
                print(f"[ROBOT-{self.robot_id}] → Immediate telemetry sent | Status: {status_to_send}")
                return True
            else:
                print(f"[ROBOT-{self.robot_id}] ✗ Immediate telemetry failed: {response.status_code}")
                return False
        except Exception as e:
            print(f"[ROBOT-{self.robot_id}] ✗ Immediate telemetry error: {e}")
            return False
    
    def check_commands(self):
        """Check for new commands from server"""
        try:
            response = self.session.get(
                f"{self.server_url}/api/robot/commands",
                params={'robot_id': self.robot_id},
                timeout=NETWORK_TIMEOUT_DEFAULT
            )
            
            if response.status_code == 200:
                try:
                    commands = response.json()
                    if commands:
                        for cmd in commands:
                            self.execute_command(cmd)
                    return True
                except ValueError as json_err:
                    print(f"[ROBOT-{self.robot_id}] ✗ Invalid JSON response from server: {json_err}")
                    print(f"[ROBOT-{self.robot_id}] Response text: {response.text[:200]}")
                    return False
            elif response.status_code == 401:
                print(f"[ROBOT-{self.robot_id}] ✗ Authentication expired. Please restart client.")
                self.running = False
                return False
            else:
                print(f"[ROBOT-{self.robot_id}] ✗ Command check failed: HTTP {response.status_code}")
                return False
        except Exception as e:
            print(f"[ROBOT-{self.robot_id}] ✗ Command check error: {e}")
            return False
    
    def execute_command(self, command):
        """Execute a command received from server"""
        cmd_type = command.get('command', '').lower()
        print(f"[ROBOT-{self.robot_id}] ← Received command: {cmd_type}")
        
        # For movement commands, validate destination before accepting
        if cmd_type in ['move_forward', 'move_up', 'move_down', 'move_left', 'move_right']:
            # Calculate where this command would move us
            test_x = self.position['x']
            test_y = self.position['y']
            
            if cmd_type == 'move_up':
                test_y -= self.speed
            elif cmd_type == 'move_down':
                test_y += self.speed
            elif cmd_type == 'move_left':
                test_x -= self.speed
            elif cmd_type == 'move_right':
                test_x += self.speed
            elif cmd_type == 'move_forward':
                rad = math.radians(self.position['orientation'])
                test_x += self.speed * math.cos(rad)
                test_y += self.speed * math.sin(rad)
            
            print(f"[ROBOT-{self.robot_id}] Testing move from ({self.position['x']:.1f}, {self.position['y']:.1f}) to ({test_x:.1f}, {test_y:.1f})")
            
            # Validate the destination
            if is_valid_position(test_x, test_y, self.obstacles):
                print(f"[ROBOT-{self.robot_id}] ✓ Position valid, accepting command")
                self.status = STATUS_MOVING
                self.motor_load = MOTOR_LOAD_MOVING
                self.current_command = cmd_type
            else:
                print(f"[ROBOT-{self.robot_id}] ✗ Command rejected: Would collide at ({test_x:.1f}, {test_y:.1f})")
                # Reject the command - stay in current state
                return
        
        elif cmd_type == 'stop' or cmd_type == 'halt':
            self.status = STATUS_STANDBY
            self.motor_load = MOTOR_LOAD_STANDBY
            self.current_command = None
        elif cmd_type == 'scan_area':
            self.status = STATUS_SCANNING
            self.motor_load = MOTOR_LOAD_SCANNING
            self.current_command = 'scan'
        else:
            print(f"[ROBOT-{self.robot_id}] Unknown command: {cmd_type}")
    
    def update_robot_state(self):
        """Update robot's internal state based on current command"""
        # Update position based on status and current command
        if self.status == STATUS_MOVING:
            # Calculate new position based on command
            new_x = self.position['x']
            new_y = self.position['y']
            
            if self.current_command == 'move_up':
                # Move up (decrease Y)
                new_y -= self.speed
            elif self.current_command == 'move_down':
                # Move down (increase Y)
                new_y += self.speed
            elif self.current_command == 'move_left':
                # Move left (decrease X)
                new_x -= self.speed
            elif self.current_command == 'move_right':
                # Move right (increase X)
                new_x += self.speed
            elif self.current_command == 'move_forward':
                # Move forward in current orientation
                rad = math.radians(self.position['orientation'])
                new_x += self.speed * math.cos(rad)
                new_y += self.speed * math.sin(rad)
                
                # Slight random orientation change for forward movement
                self.position['orientation'] += random.uniform(-5, 5)
                self.position['orientation'] = self.position['orientation'] % 360
            
            # Validate new position against obstacles
            if is_valid_position(new_x, new_y, self.obstacles):
                self.position['x'] = new_x
                self.position['y'] = new_y
            else:
                # Stop if collision detected
                print(f"[ROBOT-{self.robot_id}] Collision detected at ({new_x:.1f}, {new_y:.1f}), stopping")
                self.status = STATUS_STANDBY
                self.motor_load = MOTOR_LOAD_STANDBY
                self.current_command = None
            
            # Clear command after single execution to prevent continuous movement
            # Commands from server are one-time actions, not continuous states
            if self.current_command:
                self.status = STATUS_STANDBY
                self.motor_load = MOTOR_LOAD_STANDBY
                self.current_command = None
            
            # Battery drain
            self.battery_voltage -= MOVEMENT_BATTERY_DRAIN
            self.temperature += TEMP_INCREASE_MOVING
            
        elif self.status == STATUS_SCANNING:
            # Rotate in place
            self.position['orientation'] += 2
            self.position['orientation'] = self.position['orientation'] % 360
            self.temperature += TEMP_INCREASE_SCANNING
            
        elif self.status == STATUS_STANDBY:
            # Cool down when on standby
            if self.temperature > TEMP_MIN:
                self.temperature -= TEMP_COOLDOWN_RATE
            # Battery slowly recovers if not moving
            if self.battery_voltage < BATTERY_NOMINAL_VOLTAGE:
                self.battery_voltage += STANDBY_BATTERY_RECOVERY
        
        # Battery limits
        self.battery_voltage = max(BATTERY_MIN_VOLTAGE, min(BATTERY_MAX_VOLTAGE, self.battery_voltage))
        
        # Temperature limits
        self.temperature = max(TEMP_MIN, min(TEMP_MAX, self.temperature))
        
        # Battery warnings - stop movement if critically low
        if self.battery_voltage < BATTERY_CRITICAL_THRESHOLD:
            # Stop movement but keep current status
            if self.status == STATUS_MOVING:
                self.status = STATUS_STANDBY
            self.motor_load = MOTOR_LOAD_STANDBY
            self.current_command = None
        
        # Note: cycle_count is NOT incremented here - it only increments on power-on
    
    def get_status_with_battery_warning(self):
        """Get status string with battery warning appended if battery is low"""
        base_status = self.status
        
        # Append battery warning if voltage is low (and not already appended)
        if self.battery_voltage < BATTERY_LOW_THRESHOLD:
            if not base_status.endswith(STATUS_BATTERY_LOW_SUFFIX):
                return f"{base_status}{STATUS_BATTERY_LOW_SUFFIX}"
        else:
            # Remove battery warning if voltage recovered
            if base_status.endswith(STATUS_BATTERY_LOW_SUFFIX):
                return base_status.replace(STATUS_BATTERY_LOW_SUFFIX, '')
        
        return base_status
    
    def run_telemetry_loop(self):
        """Main loop for sending telemetry"""
        print(f"[ROBOT-{self.robot_id}] Starting telemetry loop...")
        
        while self.running and not self.stop_event.is_set():
            # Only send telemetry if authenticated
            if self.authenticated:
                # Periodically check session validity
                if self.should_check_session():
                    session_valid = self.check_session_validity()
                    if session_valid == False:  # Explicitly check for False (not None)
                        print(f"[ROBOT-{self.robot_id}] Session timeout detected. Authentication required.")
                        # Session expired, wait for re-authentication
                        time.sleep(TELEMETRY_INTERVAL)
                        continue
                
                self.update_robot_state()
                self.send_telemetry()
            else:
                # If not authenticated, just wait
                time.sleep(TELEMETRY_INTERVAL)
                continue
            
            # Check for software updates daily at midnight
            if self.should_check_versions():
                print(f"[ROBOT-{self.robot_id}] Daily version check triggered")
                self.check_software_updates()
            
            time.sleep(TELEMETRY_INTERVAL)
    
    def run_command_loop(self):
        """Loop for checking commands"""
        print(f"[ROBOT-{self.robot_id}] Starting command listener...")
        
        while self.running and not self.stop_event.is_set():
            # Only check commands if authenticated
            if self.authenticated:
                self.check_commands()
            time.sleep(COMMAND_CHECK_INTERVAL)
    
    def start(self):
        """Start the robot client"""
        # Try initial authentication
        if not self.login():
            print(f"[ROBOT-{self.robot_id}] ⚠️ Authentication failed. Waiting for manual retry from UI...")
            print(f"[ROBOT-{self.robot_id}] Please enter the correct password in the web interface.")
            # Don't return False - continue to allow UI access for password retry
        
        # Start the robot client even if authentication failed initially
        # The UI will prompt for password retry
        self.running = True
        
        # Only fetch position and check updates if authenticated
        if self.authenticated:
            # Fetch robot-specific obstacles from server
            print(f"[ROBOT-{self.robot_id}] Fetching robot-specific obstacles...")
            self.fetch_obstacles()
            
            # Fetch last known position from server
            print(f"[ROBOT-{self.robot_id}] Fetching last known position...")
            self.fetch_last_position()
            
            # Check for software updates during boot sequence
            print(f"[ROBOT-{self.robot_id}] Boot sequence: Checking for software updates...")
            self.check_software_updates()
        else:
            # If not authenticated, use fallback global obstacles
            self.obstacles = OBSTACLES
            print(f"[ROBOT-{self.robot_id}] ⚠ Not authenticated, using default global obstacles")
        
        # Start telemetry thread (will only send if authenticated)
        telemetry_thread = Thread(target=self.run_telemetry_loop, daemon=True)
        telemetry_thread.start()
        
        # Start command listener thread (will only listen if authenticated)
        command_thread = Thread(target=self.run_command_loop, daemon=True)
        command_thread.start()
        
        print(f"[ROBOT-{self.robot_id}] ✓ Client running. Press Ctrl+C to stop.")
        
        try:
            while self.running:
                time.sleep(1)
        except KeyboardInterrupt:
            print(f"\n[ROBOT-{self.robot_id}] Shutting down...")
            self.stop()
        
        return True
    
    def stop(self):
        """Stop the robot client"""
        self.running = False
        self.stop_event.set()
        print(f"[ROBOT-{self.robot_id}] ✓ Client stopped")


# Flask routes for control interface
@control_app.route('/')
def index():
    """Serve the control interface"""
    return render_template('control.html')

@control_app.route('/api/auth/status')
def auth_status():
    """Check authentication status"""
    if robot_client:
        return jsonify({
            'authenticated': robot_client.authenticated,
            'username': robot_client.username,
            'robot_id': robot_client.robot_id
        })
    return jsonify({'authenticated': False, 'error': 'Robot not initialized'}), 500

@control_app.route('/api/auth/retry', methods=['POST'])
def auth_retry():
    """Retry authentication with new password"""
    if not robot_client:
        return jsonify({'success': False, 'error': 'Robot not initialized'}), 500
    
    data = request.json
    new_password = data.get('password', '')
    
    if not new_password:
        return jsonify({'success': False, 'error': 'Password required'}), 400
    
    # Attempt authentication with new password
    success = robot_client.retry_authentication(new_password)
    
    if success:
        # Fetch obstacles, position, and check updates after successful authentication
        robot_client.fetch_obstacles()
        robot_client.fetch_last_position()
        robot_client.check_software_updates()
        return jsonify({
            'success': True,
            'message': f'Authenticated as {robot_client.username}'
        })
    else:
        return jsonify({
            'success': False,
            'error': 'Invalid credentials. Please try again.'
        }), 401

@control_app.route('/api/control/status')
def get_status():
    """Get current robot status"""
    if robot_client:
        return jsonify({
            'authenticated': robot_client.authenticated,
            'robot_id': robot_client.robot_id,
            'position': robot_client.position,
            'battery_voltage': robot_client.battery_voltage,
            'temperature': robot_client.temperature,
            'status': robot_client.get_status_with_battery_warning(),
            'motor_load': robot_client.motor_load,
            'cycle_count': robot_client.cycle_count,
            'is_powered_on': robot_client.is_powered_on
        })
    return jsonify({'error': 'Robot not initialized'}), 500

@control_app.route('/api/control/move', methods=['POST'])
def control_move():
    """Control robot position"""
    if not robot_client:
        return jsonify({'success': False, 'error': 'Robot not initialized'}), 500
    
    if not robot_client.authenticated:
        return jsonify({'success': False, 'error': 'Not authenticated'}), 401
    
    data = request.json
    direction = data.get('direction', '')
    step = 2.0  # Slower step changes
    
    # Calculate new position
    new_x = robot_client.position['x']
    new_y = robot_client.position['y']
    
    if direction == 'up':
        new_y = max(0, robot_client.position['y'] - step)  # UP decreases Y
    elif direction == 'down':
        new_y = min(100, robot_client.position['y'] + step)  # DOWN increases Y
    elif direction == 'left':
        new_x = max(0, robot_client.position['x'] - step)
    elif direction == 'right':
        new_x = min(100, robot_client.position['x'] + step)
    elif direction == 'center':
        new_x = 50.0
        new_y = 50.0
    
    # Validate new position against obstacles before updating
    if is_valid_position(new_x, new_y, robot_client.obstacles):
        robot_client.position['x'] = new_x
        robot_client.position['y'] = new_y
        return jsonify({'success': True})
    else:
        # Position would collide with obstacle
        return jsonify({
            'success': False, 
            'error': 'Collision detected',
            'message': f'Cannot move to ({new_x:.1f}, {new_y:.1f}) - obstacle in the way'
        }), 400

@control_app.route('/api/control/voltage', methods=['POST'])
def control_voltage():
    """Control battery voltage"""
    if not robot_client:
        return jsonify({'success': False, 'error': 'Robot not initialized'}), 500
    
    if not robot_client.authenticated:
        return jsonify({'success': False, 'error': 'Not authenticated'}), 401
    
    data = request.json
    voltage = data.get('voltage', 24.5)
    robot_client.battery_voltage = max(22.0, min(25.2, voltage))
    
    return jsonify({'success': True})

@control_app.route('/api/control/temperature', methods=['POST'])
def control_temperature():
    """Control temperature"""
    if not robot_client:
        return jsonify({'success': False, 'error': 'Robot not initialized'}), 500
    
    if not robot_client.authenticated:
        return jsonify({'success': False, 'error': 'Not authenticated'}), 401
    
    data = request.json
    temp = data.get('temperature', 45)
    robot_client.temperature = max(35, min(85, temp))
    
    return jsonify({'success': True})

@control_app.route('/api/control/operation', methods=['POST'])
def control_operation():
    """Control special operations"""
    if not robot_client:
        return jsonify({'success': False, 'error': 'Robot not initialized'}), 500
    
    if not robot_client.authenticated:
        return jsonify({'success': False, 'error': 'Not authenticated'}), 401
    
    data = request.json
    operation = data.get('operation', '').lower()
    
    if operation == 'charging':
        robot_client.status = STATUS_CHARGING
        robot_client.motor_load = MOTOR_LOAD_STANDBY
    elif operation == 'fault':
        robot_client.status = STATUS_FAULT
        robot_client.motor_load = MOTOR_LOAD_STANDBY
    elif operation == 'standby':
        robot_client.status = STATUS_STANDBY
        robot_client.motor_load = MOTOR_LOAD_STANDBY
    elif operation == 'moving':
        robot_client.status = STATUS_MOVING
        robot_client.motor_load = MOTOR_LOAD_MOVING
    elif operation == 'scanning':
        robot_client.status = STATUS_SCANNING
        robot_client.motor_load = MOTOR_LOAD_SCANNING
    
    return jsonify({'success': True})

@control_app.route('/api/control/power', methods=['POST'])
def control_power():
    """Toggle power on/off"""
    if not robot_client:
        return jsonify({'success': False, 'error': 'Robot not initialized'}), 500
    
    if not robot_client.authenticated:
        return jsonify({'success': False, 'error': 'Not authenticated'}), 401
    
    if robot_client.is_powered_on:
        # Turning OFF
        robot_client.status = STATUS_OFFLINE
        robot_client.motor_load = MOTOR_LOAD_STANDBY
        robot_client.is_powered_on = False
        # Send immediate telemetry before stopping
        robot_client.send_telemetry_immediate()
    else:
        # Turning ON - start with BOOTING
        robot_client.is_powered_on = True
        robot_client.status = STATUS_BOOTING
        robot_client.motor_load = 10
        
        # Increment cycle count (power-on cycle)
        robot_client.cycle_count += 1
        print(f"[ROBOT-{robot_client.robot_id}] Power-on cycle #{robot_client.cycle_count}")
        
        # Send immediate telemetry
        robot_client.send_telemetry_immediate()
        
        # Schedule transition to STANDBY after a few seconds
        import threading
        def transition_to_standby():
            import time
            time.sleep(3)  # Boot for 3 seconds
            if robot_client.is_powered_on and robot_client.status == STATUS_BOOTING:
                robot_client.status = STATUS_STANDBY
                robot_client.motor_load = MOTOR_LOAD_STANDBY
                robot_client.send_telemetry_immediate()
        
        threading.Thread(target=transition_to_standby, daemon=True).start()
    
    return jsonify({'success': True, 'is_powered_on': robot_client.is_powered_on})

@control_app.route('/api/versions/check', methods=['POST'])
def check_versions():
    """Manually trigger version check"""
    if not robot_client:
        return jsonify({'success': False, 'error': 'Robot not initialized'}), 500
    
    if not robot_client.authenticated:
        return jsonify({'success': False, 'error': 'Not authenticated'}), 401
    
    try:
        latest_versions = robot_client.check_software_updates()
        pending_updates = robot_client.db.get_pending_updates(robot_client.robot_id)
        
        return jsonify({
            'success': True,
            'latest_versions': latest_versions,
            'pending_updates': [{
                'component': update['component'],
                'current': update['current_version'],
                'available': update['available_version'],
                'notes': update['release_notes']
            } for update in pending_updates]
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@control_app.route('/api/versions/status')
def get_version_status():
    """Get current version status and available updates"""
    if not robot_client:
        return jsonify({'error': 'Robot not initialized'}), 500
    
    try:
        current_versions = robot_client.versions
        all_versions = robot_client.db.get_all_software_versions()
        pending_updates = robot_client.db.get_pending_updates(robot_client.robot_id)
        
        return jsonify({
            'current_versions': current_versions,
            'available_updates': [{
                'component': update['component'],
                'current_version': update['current_version'],
                'available_version': update['available_version'],
                'release_notes': update['release_notes']
            } for update in pending_updates],
            'version_history': [{
                'component': row['component'],
                'old_version': row['old_version'],
                'new_version': row['new_version'],
                'updated_at': row['updated_at']
            } for row in robot_client.db.get_version_history(robot_client.robot_id, 5)]
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@control_app.route('/api/versions/update', methods=['POST'])
def apply_update():
    """Apply software update for a component"""
    if not robot_client:
        return jsonify({'success': False, 'error': 'Robot not initialized'}), 500
    
    if not robot_client.authenticated:
        return jsonify({'success': False, 'error': 'Not authenticated'}), 401
    
    # Check if robot is powered on
    if not robot_client.is_powered_on:
        return jsonify({'success': False, 'error': 'Robot is powered OFF. Cannot update while powered down.'}), 400
    
    # Check if robot is in safe state (not moving/scanning)
    safe_states = [STATUS_STANDBY, STATUS_CHARGING]
    current_status = robot_client.status.replace(STATUS_BATTERY_LOW_SUFFIX, '')  # Remove battery warning
    
    if current_status not in safe_states:
        return jsonify({
            'success': False, 
            'error': f'Robot must be in STANDBY or CHARGING state. Current state: {current_status}'
        }), 400
    
    data = request.json
    component = data.get('component')
    
    if not component:
        return jsonify({'success': False, 'error': 'Component required'}), 400
    
    try:
        # Get available version from database
        version_info = robot_client.db.get_software_version(component)
        if not version_info or not version_info['available_version']:
            return jsonify({'success': False, 'error': 'No update available'}), 400
        
        new_version = version_info['available_version']
        old_version = version_info['current_version']
        
        # Apply update in database
        success = robot_client.db.apply_software_update(
            robot_client.robot_id, 
            component, 
            new_version
        )
        
        if success:
            # Update in-memory version
            robot_client.versions[component] = new_version
            
            # Send updated version to server
            robot_client.send_version_info()
            
            print(f"[ROBOT-{robot_client.robot_id}] ✓ Updated {component} from {old_version} to {new_version}")
            
            return jsonify({
                'success': True,
                'component': component,
                'old_version': old_version,
                'new_version': new_version,
                'message': f'Successfully updated {component} to {new_version}'
            })
        else:
            return jsonify({'success': False, 'error': 'Update failed'}), 500
            
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

def run_control_interface(port):
    """Run the Flask control interface"""
    print(f"[CONTROL-UI] Starting web interface on http://127.0.0.1:{port}")
    control_app.run(host='0.0.0.0', port=port, debug=False, use_reloader=False)


def initialize_robot_client(server_url=None, username=None, password=None, robot_id=None):
    """Initialize the robot client with given or default configuration"""
    global robot_client
    
    # Use provided values or fall back to module-level config
    server_url = server_url or SERVER_URL
    username = username or USERNAME
    password = password or PASSWORD
    robot_id = robot_id or ROBOT_ID
    
    # Validate credentials
    if not username or not password or username == 'MISSING_USERNAME' or password == 'MISSING_PASSWORD':
        raise ValueError("Invalid or missing credentials. Please check environment variables.")
    
    robot_client = RobotClient(server_url, username, password, robot_id)
    return robot_client


def main():
    """Main entry point for standalone execution"""
    print("=" * 60)
    print("SITARA ROBOT CLIENT")
    print("=" * 60)
    
    # Use module-level configuration
    server_url = SERVER_URL
    username = USERNAME
    password = PASSWORD
    robot_id = ROBOT_ID
    ui_port = UI_PORT
    
    # Allow command line override
    # Usage: python client_app.py [robot_id] [username] [password] [port]
    import argparse
    parser = argparse.ArgumentParser(description='SITARA Robot Client')
    parser.add_argument('robot_id', type=int, nargs='?', default=robot_id, help='Robot ID')
    parser.add_argument('username', nargs='?', default=username, help='Username')
    parser.add_argument('password', nargs='?', default=password, help='Password')
    parser.add_argument('port', type=int, nargs='?', default=ui_port, help='Control UI port (default: 5002)')
    args = parser.parse_args()
    
    # Override with command line args if provided
    robot_id = args.robot_id
    username = args.username or username
    password = args.password or password
    ui_port = args.port
    
    # Validate credentials
    if not username or not password:
        print("\n[ERROR] Missing credentials!")
        print("Please create a .env file with ROBOT_USERNAME and ROBOT_PASSWORD")
        print("See .env.example for template")
        sys.exit(1)
    
    if username.startswith('<') or username.startswith('your-') or username == 'MISSING_USERNAME':
        print("\n[ERROR] Please update .env with actual credentials!")
        print("Current username appears to be a placeholder or missing")
        sys.exit(1)
    
    print(f"Configuration:")
    print(f"  Server: {server_url}")
    print(f"  Robot ID: {robot_id}")
    print(f"  User: {username}")
    print(f"  Control UI: http://127.0.0.1:{ui_port}")
    print("=" * 60)
    
    # Initialize robot client
    try:
        initialize_robot_client(server_url, username, password, robot_id)
    except ValueError as e:
        print(f"\n[ERROR] Failed to initialize robot client: {e}")
        sys.exit(1)
    
    # Start Flask control interface in a separate thread
    ui_thread = Thread(target=run_control_interface, args=(ui_port,), daemon=True)
    ui_thread.start()
    
    # Give the UI a moment to start
    time.sleep(1)
    
    # Start the robot client (this will block)
    robot_client.start()


# ============================================================================
# AUTO-INITIALIZATION FOR WSGI/GUNICORN
# ============================================================================

def _auto_initialize_for_wsgi():
    """Auto-initialize robot client for WSGI servers like gunicorn"""
    global robot_client
    
    # Only initialize if we have valid credentials
    if USERNAME and PASSWORD and USERNAME != 'MISSING_USERNAME' and PASSWORD != 'MISSING_PASSWORD':
        if not USERNAME.startswith('<') and not USERNAME.startswith('your-'):
            try:
                print(f"[WSGI] Auto-initializing robot client...")
                robot_client = RobotClient(SERVER_URL, USERNAME, PASSWORD, ROBOT_ID)
                
                # Authenticate first (blocking to ensure it's ready)
                if robot_client.login():
                    print(f"[WSGI] ✓ Robot client authenticated")
                    robot_client.fetch_last_position()
                else:
                    print(f"[WSGI] ✗ Robot client authentication failed")
                    return
                
                # Start the robot client threads
                robot_client.running = True
                
                # Start telemetry thread
                telemetry_thread = Thread(target=robot_client.run_telemetry_loop, daemon=True)
                telemetry_thread.start()
                
                # Start command listener thread  
                command_thread = Thread(target=robot_client.run_command_loop, daemon=True)
                command_thread.start()
                
                print(f"[WSGI] ✓ Robot client fully initialized and running")
                
            except Exception as e:
                print(f"[WSGI] ✗ Failed to auto-initialize robot client: {e}")
                import traceback
                traceback.print_exc()
                robot_client = None
        else:
            print(f"[WSGI] Skipping auto-initialization: credentials appear to be placeholders")
    else:
        print(f"[WSGI] Skipping auto-initialization: missing or invalid credentials")

# Trigger auto-initialization when imported by gunicorn
# This is skipped when running as __main__ because main() handles it
if __name__ != "__main__":
    print(f"[INIT] Module imported (not running as __main__), triggering auto-initialization...")
    _auto_initialize_for_wsgi()


if __name__ == "__main__":
    main()
