"""
SITARA Robot Client Application
Simulates a robot that connects to the server, sends telemetry, and receives commands.
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
import sys

# Load environment variables
# Priority: .env (personal credentials) -> config.env (defaults/template)
if os.path.exists('.env'):
    print("[CONFIG] Loading credentials from .env")
    load_dotenv('.env')
else:
    print("[CONFIG] .env not found, loading from config.env")
    load_dotenv('config.env')

class RobotClient:
    def __init__(self, server_url, username, password, robot_id=1):
        self.server_url = server_url.rstrip('/')
        self.username = username
        self.password = password
        self.robot_id = robot_id
        self.session = requests.Session()
        self.running = False
        self.stop_event = Event()
        
        # Robot state
        self.position = {'x': 50.0, 'y': 50.0, 'orientation': 0.0}
        self.battery_voltage = 24.5
        self.temperature = 45.0
        self.motor_load = 0
        self.status = "IDLE"
        self.cycle_count = 0
        
        # Movement parameters
        self.speed = 1.0  # units per update
        self.current_command = None
        
        print(f"[ROBOT-{self.robot_id}] Initializing client...")
    
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
            
            if response.status_code in [200, 302]:
                print(f"[ROBOT-{self.robot_id}] ✓ Authenticated as {self.username}")
                return True
            else:
                print(f"[ROBOT-{self.robot_id}] ✗ Authentication failed: {response.status_code}")
                return False
        except Exception as e:
            print(f"[ROBOT-{self.robot_id}] ✗ Login error: {e}")
            return False
    
    def send_telemetry(self):
        """Send current telemetry data to server"""
        try:
            # Generate timestamp on client side for accurate time tracking
            timestamp = datetime.now(timezone.utc).isoformat()
            
            telemetry_data = {
                'robot_id': self.robot_id,
                'battery_voltage': round(self.battery_voltage, 2),
                'temperature': round(self.temperature, 1),
                'motor_load': self.motor_load,
                'status': self.status,
                'cycle_count': self.cycle_count,
                'x': round(self.position['x'], 2),
                'y': round(self.position['y'], 2),
                'orientation': round(self.position['orientation'], 2),
                'timestamp': timestamp  # Client-generated timestamp
            }
            
            response = self.session.post(
                f"{self.server_url}/api/robot/telemetry",
                json=telemetry_data,
                timeout=5
            )
            
            if response.status_code == 200:
                print(f"[ROBOT-{self.robot_id}] → Telemetry sent | Status: {self.status} | Pos: ({self.position['x']:.1f}, {self.position['y']:.1f}) | Battery: {self.battery_voltage:.2f}V")
                return True
            else:
                print(f"[ROBOT-{self.robot_id}] ✗ Telemetry failed: {response.status_code}")
                return False
        except Exception as e:
            print(f"[ROBOT-{self.robot_id}] ✗ Telemetry error: {e}")
            return False
    
    def check_commands(self):
        """Check for new commands from server"""
        try:
            response = self.session.get(
                f"{self.server_url}/api/robot/commands",
                params={'robot_id': self.robot_id},
                timeout=5
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
        
        if cmd_type == 'move_forward':
            self.status = "MOVING"
            self.motor_load = 65
            self.current_command = 'move_forward'
        elif cmd_type == 'stop' or cmd_type == 'halt':
            self.status = "IDLE"
            self.motor_load = 0
            self.current_command = None
        elif cmd_type == 'scan_area':
            self.status = "SCANNING"
            self.motor_load = 30
            self.current_command = 'scan'
        else:
            print(f"[ROBOT-{self.robot_id}] Unknown command: {cmd_type}")
    
    def update_robot_state(self):
        """Update robot's internal state based on current command"""
        # Update position based on status
        if self.status == "MOVING":
            # Move forward in current orientation
            rad = math.radians(self.position['orientation'])
            self.position['x'] += self.speed * math.cos(rad)
            self.position['y'] += self.speed * math.sin(rad)
            
            # Keep within bounds (0-100)
            self.position['x'] = max(0, min(100, self.position['x']))
            self.position['y'] = max(0, min(100, self.position['y']))
            
            # Slight random orientation change
            self.position['orientation'] += random.uniform(-5, 5)
            self.position['orientation'] = self.position['orientation'] % 360
            
            # Battery drain
            self.battery_voltage -= 0.001
            self.temperature += 0.1
            
        elif self.status == "SCANNING":
            # Rotate in place
            self.position['orientation'] += 2
            self.position['orientation'] = self.position['orientation'] % 360
            self.temperature += 0.05
            
        elif self.status == "IDLE":
            # Cool down when idle
            if self.temperature > 40:
                self.temperature -= 0.2
            # Battery slowly recovers if not moving
            if self.battery_voltage < 24.5:
                self.battery_voltage += 0.002
        
        # Battery limits
        self.battery_voltage = max(22.0, min(25.2, self.battery_voltage))
        
        # Temperature limits
        self.temperature = max(35, min(85, self.temperature))
        
        # Battery warnings
        if self.battery_voltage < 23.0:
            self.status = "BATTERY LOW"
            self.motor_load = 0
        
        # Update cycle count
        self.cycle_count += 1
    
    def run_telemetry_loop(self):
        """Main loop for sending telemetry"""
        print(f"[ROBOT-{self.robot_id}] Starting telemetry loop...")
        
        while self.running and not self.stop_event.is_set():
            self.update_robot_state()
            self.send_telemetry()
            time.sleep(2)  # Send telemetry every 2 seconds
    
    def run_command_loop(self):
        """Loop for checking commands"""
        print(f"[ROBOT-{self.robot_id}] Starting command listener...")
        
        while self.running and not self.stop_event.is_set():
            self.check_commands()
            time.sleep(3)  # Check for commands every 3 seconds
    
    def start(self):
        """Start the robot client"""
        if not self.login():
            print(f"[ROBOT-{self.robot_id}] Cannot start without authentication")
            return False
        
        self.running = True
        
        # Start telemetry thread
        telemetry_thread = Thread(target=self.run_telemetry_loop, daemon=True)
        telemetry_thread.start()
        
        # Start command listener thread
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


def main():
    """Main entry point"""
    print("=" * 60)
    print("SITARA ROBOT CLIENT")
    print("=" * 60)
    
    # Configuration from environment variables
    # Note: Using ROBOT_USERNAME/ROBOT_PASSWORD to avoid conflicts with Windows USERNAME env var
    SERVER_URL = os.getenv('SERVER_URL', 'http://127.0.0.1:5001')
    USERNAME = os.getenv('ROBOT_USERNAME')
    PASSWORD = os.getenv('ROBOT_PASSWORD')
    ROBOT_ID = int(os.getenv('ROBOT_ID', '1'))
    
    # Validate required credentials
    if not USERNAME or not PASSWORD:
        print("\n[ERROR] Missing credentials!")
        print("Please create a .env file with ROBOT_USERNAME and ROBOT_PASSWORD")
        print("See .env.example for template")
        sys.exit(1)
    
    if USERNAME.startswith('<') or USERNAME.startswith('your-'):
        print("\n[ERROR] Please update .env with actual credentials!")
        print("Current username appears to be a placeholder")
        sys.exit(1)
    
    # Allow command line override
    if len(sys.argv) > 1:
        ROBOT_ID = int(sys.argv[1])
    if len(sys.argv) > 2:
        USERNAME = sys.argv[2]
    if len(sys.argv) > 3:
        PASSWORD = sys.argv[3]
    
    print(f"Configuration:")
    print(f"  Server: {SERVER_URL}")
    print(f"  Robot ID: {ROBOT_ID}")
    print(f"  User: {USERNAME}")
    print("=" * 60)
    
    # Create and start client
    client = RobotClient(SERVER_URL, USERNAME, PASSWORD, ROBOT_ID)
    client.start()


if __name__ == "__main__":
    main()
