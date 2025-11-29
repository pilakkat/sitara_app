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
from flask import Flask, render_template_string, request, jsonify
import sys

# Load environment variables
# Priority: .env (personal credentials) -> config.env (defaults/template)
if os.path.exists('.env'):
    print("[CONFIG] Loading credentials from .env")
    load_dotenv('.env')
else:
    print("[CONFIG] .env not found, loading from config.env")
    load_dotenv('config.env')

# Flask app for control interface
control_app = Flask(__name__)
robot_client = None  # Will be set after initialization

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
        self.status = "STANDBY"
        self.cycle_count = 0
        
        # Track previous state for change detection
        self.last_telemetry_state = None
        
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
    
    def fetch_last_position(self):
        """Fetch the last known position from the server"""
        try:
            response = self.session.get(
                f"{self.server_url}/api/telemetry",
                params={'robot_id': self.robot_id},
                timeout=5
            )
            
            if response.status_code == 200:
                data = response.json()
                if data and 'pos_x' in data and 'pos_y' in data:
                    self.position['x'] = data.get('pos_x', 50.0)
                    self.position['y'] = data.get('pos_y', 50.0)
                    self.position['orientation'] = data.get('orientation', 0.0)
                    print(f"[ROBOT-{self.robot_id}] ✓ Restored last position: ({self.position['x']:.1f}, {self.position['y']:.1f}), orientation: {self.position['orientation']:.1f}°")
                    
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
        try:
            # Generate timestamp on client side for accurate time tracking
            timestamp = datetime.now(timezone.utc).isoformat()
            
            # Current state (excluding timestamp for comparison)
            current_state = {
                'robot_id': self.robot_id,
                'battery_voltage': round(self.battery_voltage, 2),
                'temperature': round(self.temperature, 1),
                'motor_load': self.motor_load,
                'status': self.status,
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
                timeout=5
            )
            
            if response.status_code == 200:
                # Update last sent state
                self.last_telemetry_state = current_state
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
            self.status = "STANDBY"
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
            
        elif self.status == "STANDBY":
            # Cool down when on standby
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
            time.sleep(5)  # Send telemetry every 5 seconds
    
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
        
        # Fetch last known position from server
        print(f"[ROBOT-{self.robot_id}] Fetching last known position...")
        self.fetch_last_position()
        
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


# Flask routes for control interface
@control_app.route('/')
def index():
    """Serve the control interface"""
    html = """
    <!DOCTYPE html>
    <html>
    <head>
        <title>SITARA Robot Client Control</title>
        <meta charset="UTF-8">
        <link href="https://fonts.googleapis.com/css2?family=Orbitron:wght@400;700&family=Roboto:wght@300;400;500&display=swap" rel="stylesheet">
        <style>
            :root {
                --bg-dark: #000000;
                --neon-blue: #00f3ff;
                --neon-purple: #bc13fe;
                --dim-blue: #45a29e;
                --text-main: #ffffff;
                --text-secondary: #e0e0e0;
                --text-muted: #b0b0b0;
                --font-head: 'Orbitron', sans-serif;
                --font-body: 'Roboto', sans-serif;
                --glass-bg: rgba(20, 20, 30, 0.75);
                --glass-border: rgba(0, 243, 255, 0.2);
                --glass-blur: 15px;
            }
            
            * { margin: 0; padding: 0; box-sizing: border-box; }
            body {
                font-family: var(--font-body);
                background: var(--bg-dark);
                background-image: radial-gradient(circle at 20% 50%, rgba(0, 243, 255, 0.05) 0%, transparent 50%),
                                  radial-gradient(circle at 80% 80%, rgba(188, 19, 254, 0.05) 0%, transparent 50%);
                color: var(--text-main);
                padding: 20px;
                min-height: 100vh;
            }
            .container {
                max-width: 900px;
                margin: 0 auto;
                background: var(--glass-bg);
                backdrop-filter: blur(var(--glass-blur));
                border: 1px solid var(--glass-border);
                border-radius: 20px;
                padding: 30px;
                box-shadow: 0 8px 32px 0 rgba(0, 0, 0, 0.5);
            }
            h1 {
                text-align: center;
                margin-bottom: 10px;
                font-size: 2.5em;
                font-family: var(--font-head);
                color: var(--neon-blue);
                text-shadow: 0 0 20px rgba(0, 243, 255, 0.5);
            }
            .robot-id {
                text-align: center;
                font-size: 1.2em;
                color: var(--text-secondary);
                margin-bottom: 30px;
            }
            .section {
                background: rgba(0, 0, 0, 0.3);
                border: 1px solid rgba(0, 243, 255, 0.2);
                border-radius: 15px;
                padding: 20px;
                margin-bottom: 20px;
            }
            .section h2 {
                margin-bottom: 15px;
                font-size: 1.5em;
                font-family: var(--font-head);
                color: var(--neon-blue);
                border-bottom: 2px solid rgba(0, 243, 255, 0.3);
                padding-bottom: 10px;
            }
            .control-grid {
                display: grid;
                grid-template-columns: repeat(3, 1fr);
                gap: 10px;
                max-width: 300px;
                margin: 0 auto;
            }
            .controls-row {
                display: grid;
                grid-template-columns: 1fr 1fr;
                gap: 30px;
                margin: 20px 0;
            }
            .control-panel {
                display: flex;
                flex-direction: column;
                align-items: center;
            }
            .sliders-container {
                display: flex;
                gap: 40px;
                justify-content: center;
                align-items: center;
                min-height: 250px;
            }
            .vertical-slider-group {
                display: flex;
                flex-direction: column;
                align-items: center;
                gap: 15px;
            }
            .slider-label {
                text-align: center;
                font-size: 0.95em;
                color: var(--text-muted);
            }
            .slider-value {
                font-size: 1.3em;
                font-weight: bold;
                color: var(--neon-blue);
                margin-bottom: 10px;
            }
            .vertical-slider {
                writing-mode: bt-lr; /* IE */
                -webkit-appearance: slider-vertical; /* WebKit */
                width: 8px;
                height: 200px;
                padding: 0;
                margin: 0;
                border-radius: 5px;
                background: rgba(0, 243, 255, 0.2);
                outline: none;
            }
            .vertical-slider::-webkit-slider-thumb {
                -webkit-appearance: none;
                appearance: none;
                width: 25px;
                height: 25px;
                border-radius: 50%;
                background: var(--neon-blue);
                cursor: pointer;
                box-shadow: 0 0 10px var(--neon-blue);
            }
            .vertical-slider::-moz-range-thumb {
                width: 25px;
                height: 25px;
                border-radius: 50%;
                background: var(--neon-blue);
                cursor: pointer;
                border: none;
                box-shadow: 0 0 10px var(--neon-blue);
            }
            .btn {
                background: rgba(0, 243, 255, 0.1);
                border: 1px solid var(--neon-blue);
                color: var(--neon-blue);
                padding: 15px;
                border-radius: 10px;
                cursor: pointer;
                font-size: 1.1em;
                font-weight: bold;
                font-family: var(--font-head);
                transition: all 0.3s;
                text-align: center;
            }
            .btn:hover {
                background: var(--neon-blue);
                color: #000;
                transform: translateY(-2px);
                box-shadow: 0 0 20px var(--neon-blue);
            }
            .btn:active {
                transform: translateY(0);
            }
            .btn-special {
                background: rgba(255, 100, 100, 0.1);
                border-color: rgba(255, 100, 100, 0.8);
                color: rgba(255, 150, 150, 1);
            }
            .btn-special:hover {
                background: rgba(255, 100, 100, 0.3);
                color: #fff;
            }
            .btn-charge {
                background: rgba(100, 255, 100, 0.1);
                border-color: rgba(100, 255, 100, 0.8);
                color: rgba(100, 255, 100, 1);
            }
            .btn-charge:hover {
                background: rgba(100, 255, 100, 0.3);
                color: #000;
            }
            .status-display {
                display: grid;
                grid-template-columns: repeat(2, 1fr);
                gap: 15px;
                margin-top: 20px;
            }
            .status-item {
                background: rgba(0, 0, 0, 0.4);
                border: 1px solid rgba(0, 243, 255, 0.2);
                padding: 15px;
                border-radius: 10px;
                text-align: center;
            }
            .status-label {
                font-size: 0.9em;
                color: var(--text-muted);
                margin-bottom: 5px;
            }
            .status-value {
                font-size: 1.5em;
                font-weight: bold;
            }
            .special-ops {
                display: grid;
                grid-template-columns: repeat(3, 1fr);
                gap: 10px;
                margin-top: 15px;
            }
            .message {
                text-align: center;
                padding: 10px;
                margin-top: 15px;
                border-radius: 8px;
                background: rgba(255, 255, 255, 0.2);
                display: none;
            }
            .message.show {
                display: block;
            }
        </style>
    </head>
    <body>
        <div class="container">
            <h1>🤖 SITARA ROBOT CONTROL</h1>
            <div class="robot-id">Robot ID: <span id="robotId">Loading...</span></div>
            
            <div class="controls-row">
                <div class="control-panel">
                    <h2>📍 Position Control</h2>
                    <div class="control-grid">
                        <div></div>
                        <button class="btn" onclick="moveDirection('up')">▲<br>UP</button>
                        <div></div>
                        <button class="btn" onclick="moveDirection('left')">◀<br>LEFT</button>
                        <div></div>
                        <button class="btn" onclick="moveDirection('right')">▶<br>RIGHT</button>
                        <div></div>
                        <button class="btn" onclick="moveDirection('down')">▼<br>DOWN</button>
                        <div></div>
                    </div>
                </div>
                
                <div class="control-panel">
                    <h2>⚡ System Parameters</h2>
                    <div class="sliders-container">
                        <div class="vertical-slider-group">
                            <div class="slider-label">Battery Voltage</div>
                            <div class="slider-value" id="voltageValue">24.5V</div>
                            <input type="range" class="vertical-slider" id="voltageSlider" 
                                   min="22" max="25.2" step="0.1" value="24.5"
                                   orient="vertical"
                                   oninput="updateVoltage(this.value)">
                        </div>
                        <div class="vertical-slider-group">
                            <div class="slider-label">Temperature</div>
                            <div class="slider-value" id="tempValue">45°C</div>
                            <input type="range" class="vertical-slider" id="tempSlider" 
                                   min="35" max="85" step="1" value="45"
                                   orient="vertical"
                                   oninput="updateTemperature(this.value)">
                        </div>
                    </div>
                </div>
            </div>
            
            <div class="section">
                <h2>🔧 Special Operations</h2>
                <div class="special-ops">
                    <button class="btn btn-charge" onclick="specialOp('charging')">🔋 CHARGING</button>
                    <button class="btn btn-special" onclick="specialOp('turnoff')">⏻ TURN OFF</button>
                    <button class="btn btn-special" onclick="specialOp('fault')">⚠️ FAULT</button>
                    <button class="btn" onclick="specialOp('standby')">⏸️ STANDBY</button>
                    <button class="btn" onclick="specialOp('moving')">▶️ MOVING</button>
                    <button class="btn" onclick="specialOp('scanning')">🔍 SCANNING</button>
                </div>
            </div>
            
            <div class="section">
                <h2>📊 Current Status</h2>
                <div class="status-display">
                    <div class="status-item">
                        <div class="status-label">Position</div>
                        <div class="status-value" id="positionValue">50, 50</div>
                    </div>
                    <div class="status-item">
                        <div class="status-label">Orientation</div>
                        <div class="status-value" id="orientationValue">0°</div>
                    </div>
                    <div class="status-item">
                        <div class="status-label">Battery</div>
                        <div class="status-value" id="batteryValue">24.5V</div>
                    </div>
                    <div class="status-item">
                        <div class="status-label">Temperature</div>
                        <div class="status-value" id="temperatureValue">45°C</div>
                    </div>
                    <div class="status-item">
                        <div class="status-label">Status</div>
                        <div class="status-value" id="statusValue">STANDBY</div>
                    </div>
                    <div class="status-item">
                        <div class="status-label">Cycle Count</div>
                        <div class="status-value" id="cyclesValue">0</div>
                    </div>
                </div>
            </div>
            
            <div class="message" id="message"></div>
        </div>
        
        <script>
            function showMessage(text) {
                const msg = document.getElementById('message');
                msg.textContent = text;
                msg.classList.add('show');
                setTimeout(() => msg.classList.remove('show'), 3000);
            }
            
            function moveDirection(dir) {
                fetch('/api/control/move', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({direction: dir})
                })
                .then(r => r.json())
                .then(data => {
                    if (data.success) {
                        showMessage('Position updated: ' + dir.toUpperCase());
                        updateStatus();
                    }
                });
            }
            
            function updateVoltage(value) {
                document.getElementById('voltageValue').textContent = value + 'V';
                fetch('/api/control/voltage', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({voltage: parseFloat(value)})
                })
                .then(r => r.json())
                .then(data => {
                    if (data.success) updateStatus();
                });
            }
            
            function updateTemperature(value) {
                document.getElementById('tempValue').textContent = value + '°C';
                fetch('/api/control/temperature', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({temperature: parseInt(value)})
                })
                .then(r => r.json())
                .then(data => {
                    if (data.success) updateStatus();
                });
            }
            
            function specialOp(operation) {
                fetch('/api/control/operation', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({operation: operation})
                })
                .then(r => r.json())
                .then(data => {
                    if (data.success) {
                        showMessage('Operation: ' + operation.toUpperCase());
                        updateStatus();
                    }
                });
            }
            
            function updateStatus() {
                fetch('/api/control/status')
                .then(r => r.json())
                .then(data => {
                    document.getElementById('robotId').textContent = data.robot_id;
                    document.getElementById('positionValue').textContent = 
                        data.position.x.toFixed(1) + ', ' + data.position.y.toFixed(1);
                    document.getElementById('orientationValue').textContent = 
                        data.position.orientation.toFixed(1) + '°';
                    document.getElementById('batteryValue').textContent = 
                        data.battery_voltage.toFixed(2) + 'V';
                    document.getElementById('temperatureValue').textContent = 
                        data.temperature.toFixed(1) + '°C';
                    document.getElementById('statusValue').textContent = data.status;
                    document.getElementById('cyclesValue').textContent = data.cycle_count;
                    
                    // Update sliders
                    document.getElementById('voltageSlider').value = data.battery_voltage;
                    document.getElementById('tempSlider').value = data.temperature;
                });
            }
            
            // Update status every 5 seconds
            setInterval(updateStatus, 5000);
            updateStatus();
        </script>
    </body>
    </html>
    """
    return html

@control_app.route('/api/control/status')
def get_status():
    """Get current robot status"""
    if robot_client:
        return jsonify({
            'robot_id': robot_client.robot_id,
            'position': robot_client.position,
            'battery_voltage': robot_client.battery_voltage,
            'temperature': robot_client.temperature,
            'status': robot_client.status,
            'motor_load': robot_client.motor_load,
            'cycle_count': robot_client.cycle_count
        })
    return jsonify({'error': 'Robot not initialized'}), 500

@control_app.route('/api/control/move', methods=['POST'])
def control_move():
    """Control robot position"""
    if not robot_client:
        return jsonify({'success': False, 'error': 'Robot not initialized'}), 500
    
    data = request.json
    direction = data.get('direction', '')
    step = 2.0  # Slower step changes
    
    if direction == 'up':
        robot_client.position['y'] = max(0, robot_client.position['y'] - step)  # UP decreases Y
    elif direction == 'down':
        robot_client.position['y'] = min(100, robot_client.position['y'] + step)  # DOWN increases Y
    elif direction == 'left':
        robot_client.position['x'] = max(0, robot_client.position['x'] - step)
    elif direction == 'right':
        robot_client.position['x'] = min(100, robot_client.position['x'] + step)
    elif direction == 'center':
        robot_client.position['x'] = 50.0
        robot_client.position['y'] = 50.0
    
    return jsonify({'success': True})

@control_app.route('/api/control/voltage', methods=['POST'])
def control_voltage():
    """Control battery voltage"""
    if not robot_client:
        return jsonify({'success': False, 'error': 'Robot not initialized'}), 500
    
    data = request.json
    voltage = data.get('voltage', 24.5)
    robot_client.battery_voltage = max(22.0, min(25.2, voltage))
    
    return jsonify({'success': True})

@control_app.route('/api/control/temperature', methods=['POST'])
def control_temperature():
    """Control temperature"""
    if not robot_client:
        return jsonify({'success': False, 'error': 'Robot not initialized'}), 500
    
    data = request.json
    temp = data.get('temperature', 45)
    robot_client.temperature = max(35, min(85, temp))
    
    return jsonify({'success': True})

@control_app.route('/api/control/operation', methods=['POST'])
def control_operation():
    """Control special operations"""
    if not robot_client:
        return jsonify({'success': False, 'error': 'Robot not initialized'}), 500
    
    data = request.json
    operation = data.get('operation', '').lower()
    
    if operation == 'charging':
        robot_client.status = 'CHARGING'
        robot_client.motor_load = 0
    elif operation == 'turnoff':
        robot_client.status = 'OFFLINE'
        robot_client.motor_load = 0
    elif operation == 'fault':
        robot_client.status = 'FAULT'
        robot_client.motor_load = 0
    elif operation == 'standby':
        robot_client.status = 'STANDBY'
        robot_client.motor_load = 0
    elif operation == 'moving':
        robot_client.status = 'MOVING'
        robot_client.motor_load = 65
    elif operation == 'scanning':
        robot_client.status = 'SCANNING'
        robot_client.motor_load = 30
    
    return jsonify({'success': True})

def run_control_interface(port):
    """Run the Flask control interface"""
    print(f"[CONTROL-UI] Starting web interface on http://127.0.0.1:{port}")
    control_app.run(host='0.0.0.0', port=port, debug=False, use_reloader=False)


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
    
    # Get control UI port
    UI_PORT = int(os.getenv('CLIENT_UI_PORT', '5002'))
    
    # Allow command line override
    # Usage: python client_app.py [robot_id] [username] [password] [--port PORT]
    import argparse
    parser = argparse.ArgumentParser(description='SITARA Robot Client')
    parser.add_argument('robot_id', type=int, nargs='?', default=ROBOT_ID, help='Robot ID')
    parser.add_argument('username', nargs='?', default=USERNAME, help='Username')
    parser.add_argument('password', nargs='?', default=PASSWORD, help='Password')
    parser.add_argument('--port', '-p', type=int, default=UI_PORT, help='Control UI port (default: 5002)')
    args = parser.parse_args()
    
    ROBOT_ID = args.robot_id
    USERNAME = args.username or USERNAME
    PASSWORD = args.password or PASSWORD
    UI_PORT = args.port
    
    print(f"Configuration:")
    print(f"  Server: {SERVER_URL}")
    print(f"  Robot ID: {ROBOT_ID}")
    print(f"  User: {USERNAME}")
    print(f"  Control UI: http://127.0.0.1:{UI_PORT}")
    print("=" * 60)
    
    # Create and start client
    global robot_client
    robot_client = RobotClient(SERVER_URL, USERNAME, PASSWORD, ROBOT_ID)
    
    # Start Flask control interface in a separate thread
    ui_thread = Thread(target=run_control_interface, args=(UI_PORT,), daemon=True)
    ui_thread.start()
    
    # Give the UI a moment to start
    time.sleep(1)
    
    # Start the robot client (this will block)
    robot_client.start()


if __name__ == "__main__":
    main()
