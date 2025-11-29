from flask import Flask, render_template, request, jsonify, redirect, url_for
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from flask_sqlalchemy import SQLAlchemy
from dotenv import load_dotenv
from datetime import datetime, timedelta, timezone
import random, os

# Load environment variables from .env file
load_dotenv()

app = Flask(__name__)
app.secret_key = os.getenv('SECRET_KEY', os.urandom(24).hex())  # Load from environment variable

# Database Config
basedir = os.path.abspath(os.path.dirname(__file__))
default_db_path = 'sqlite:///' + os.path.join(basedir, 'database/sitara.db')
app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv('DATABASE_URL', default_db_path)
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

# --- Models ---
class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(150), unique=True, nullable=False)
    password = db.Column(db.String(150), nullable=False) # In prod, hash this!

# --- 1. Robot Identity (The "Thing") ---
class Robot(db.Model):
    __tablename__ = 'robots'
    id = db.Column(db.Integer, primary_key=True)
    serial_number = db.Column(db.String(50), unique=True, nullable=False)
    model_type = db.Column(db.String(20), default="32DOF-HUMANOID")
    # Link to the user (Operator)
    assigned_to = db.Column(db.Integer, db.ForeignKey('user.id'))
    
    # Relationships
    telemetry = db.relationship('TelemetryLog', backref='robot', lazy='dynamic')
    path_history = db.relationship('PathLog', backref='robot', lazy='dynamic')

# --- 2. Health & Status (The "Slow" Time Series) ---
class TelemetryLog(db.Model):
    __tablename__ = 'telemetry_logs'
    id = db.Column(db.Integer, primary_key=True)
    robot_id = db.Column(db.Integer, db.ForeignKey('robots.id'), nullable=False)
    timestamp = db.Column(db.DateTime, default=datetime.now(timezone.utc), index=True) # Indexed for speed
    
    # The Data Points
    battery_voltage = db.Column(db.Float)   # e.g., 24.5
    cpu_temp = db.Column(db.Integer)        # e.g., 65
    motor_load = db.Column(db.Integer)      # e.g., 40 (%)
    cycle_counter = db.Column(db.BigInteger)# Operation Time in seconds
    status_code = db.Column(db.String(20))  # e.g., "NOMINAL", "ERR_JOINT_4"

# --- 3. Map/Spatial History (The "Fast" Time Series) ---
class PathLog(db.Model):
    __tablename__ = 'path_logs'
    id = db.Column(db.Integer, primary_key=True)
    robot_id = db.Column(db.Integer, db.ForeignKey('robots.id'), nullable=False)
    timestamp = db.Column(db.DateTime, default=datetime.now(timezone.utc), index=True)
    
    # Spatial Data (Normalized 0-100% or Meters)
    pos_x = db.Column(db.Float)
    pos_y = db.Column(db.Float)
    orientation = db.Column(db.Float)       # Heading in degrees (0-360)


# --- Data from S1/S2 Streams) ---
@app.route('/api/telemetry', methods=['POST'])
@login_required 
def get_robot_telemetry():
    data = request.json
    robot_serial = data.get('serial') # Assume S1 sends this
    
    robot = Robot.query.filter_by(serial_number=robot_serial).first()
    if not robot:
        return jsonify({"error": "Unknown Robot"}), 404

    # --- CONSTRAINT 1: Cooldown & Change Detection ---
    # Get the last log for this robot
    last_log = TelemetryLog.query.filter_by(robot_id=robot.id).order_by(TelemetryLog.timestamp.desc()).first()
    
    should_log = False
    current_time = datetime.now(timezone.utc)

    if not last_log:
        should_log = True
    else:
        # Check time difference (Cooldown)
        time_diff = (current_time - last_log.timestamp).total_seconds()
        
        # Check if values changed significantly
        values_changed = (
            abs(last_log.battery_voltage - data['battery']) > 0.1 or 
            abs(last_log.cpu_temp - data['cpu_temp']) > 1 or
            last_log.status_code != data['status']
        )

        # Logic: Log if (Time > 1 min AND Values Changed) OR (Time > 1 hour [KeepAlive])
        if time_diff > 60 and values_changed:
            should_log = True
        elif time_diff > 3600: # Force a log every hour even if nothing changes
            should_log = True

    if should_log:
        new_log = TelemetryLog(
            robot_id=robot.id,
            battery_voltage=data['battery'],
            cpu_temp=data['cpu_temp'],
            motor_load=data['load'],
            cycle_counter=data['cycles'],
            status_code=data['status'],
            timestamp=current_time
        )
        db.session.add(new_log)

    # --- ALWAYS Log Path (Map needs higher resolution) ---
    # We log path independently because we want smooth movement history
    # even if battery/temp hasn't changed.
    # Use a fresh timestamp to ensure uniqueness
    new_path = PathLog(
        robot_id=robot.id,
        pos_x=data['pos_x'],
        pos_y=data['pos_y'],
        timestamp=datetime.now(timezone.utc)
    )
    db.session.add(new_path)
    
    db.session.commit()
    return jsonify({"msg": "Synced"}), 200

def cleanup_old_data():
    """Deletes logs older than 7 days"""
    expiration_date = datetime.now(timezone.utc) - timedelta(days=30)
    
    # Delete old telemetry
    TelemetryLog.query.filter(TelemetryLog.timestamp < expiration_date).delete()
    
    # Delete old path history
    PathLog.query.filter(PathLog.timestamp < expiration_date).delete()
    
    db.session.commit()
    print("System Maintenance: Old logs purged.")

# --- Routes ---

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

def user_can_access_robot(robot_id):
    """Check if current user has access to the specified robot"""
    robot = Robot.query.get(robot_id)
    if not robot:
        return False
    
    # Admin (username='admin') can access all robots
    if current_user.username == 'admin':
        return True
    
    # Operators can only access their assigned robots
    return robot.assigned_to == current_user.id

def get_user_accessible_robots():
    """Get list of robot IDs the current user can access"""
    if current_user.username == 'admin':
        # Admin sees all robots
        return [r.id for r in Robot.query.all()]
    else:
        # Operators see only their assigned robots
        return [r.id for r in Robot.query.filter_by(assigned_to=current_user.id).all()]

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        user = User.query.filter_by(username=username).first()
        if user and user.password == password: # Plaintext for hackathon speed
            login_user(user)
            return redirect(url_for('dashboard'))
    return render_template('login.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('index'))

@app.route('/dashboard')
@login_required
def dashboard():
    return render_template('dashboard.html', name=current_user.username)

@app.route('/terms')
def terms():
    return render_template('terms.html')

@app.route('/privacy')
def privacy():
    return render_template('privacy.html')

@app.route('/ethics')
def ethics():
    return render_template('ethics.html')

# --- APIs (AJAX Hooks) ---

@app.route('/api/telemetry')
@login_required
def api_telemetry():
    """GET endpoint - Returns latest telemetry data for dashboard"""
    # Get robot_id from query parameter, default to first accessible robot
    robot_id = request.args.get('robot_id', type=int)
    
    if robot_id:
        # Check access permission
        if not user_can_access_robot(robot_id):
            return jsonify({"error": "Access denied to this robot"}), 403
        robot = Robot.query.get(robot_id)
    else:
        # Get first accessible robot
        accessible_ids = get_user_accessible_robots()
        if not accessible_ids:
            return jsonify({
                "battery": 0,
                "cpu_temp": 0,
                "load": 0,
                "status": "NO_ROBOT_ACCESS",
                "pos_x": 50,
                "pos_y": 50,
                "cycles": 0
            })
        robot = Robot.query.get(accessible_ids[0])
    
    if not robot:
        return jsonify({
            "battery": 0,
            "cpu_temp": 0,
            "load": 0,
            "status": "NO_ROBOT_FOUND",
            "pos_x": 50,
            "pos_y": 50,
            "cycles": 0
        })
    
    # Get latest telemetry
    latest_telem = TelemetryLog.query.filter_by(robot_id=robot.id).order_by(TelemetryLog.timestamp.desc()).first()
    
    # Get latest position
    latest_path = PathLog.query.filter_by(robot_id=robot.id).order_by(PathLog.timestamp.desc()).first()
    
    if not latest_telem:
        return jsonify({
            "battery": 0,
            "cpu_temp": 0,
            "load": 0,
            "status": "NO_DATA",
            "pos_x": 50,
            "pos_y": 50,
            "cycles": 0
        })
    
    return jsonify({
        "robot_id": robot.id,
        "serial_number": robot.serial_number,
        "battery": latest_telem.battery_voltage or 0,
        "cpu_temp": latest_telem.cpu_temp or 0,
        "load": latest_telem.motor_load or 0,
        "status": latest_telem.status_code or "UNKNOWN",
        "pos_x": latest_path.pos_x if latest_path else 50,
        "pos_y": latest_path.pos_y if latest_path else 50,
        "orientation": latest_path.orientation if latest_path else 0,
        "cycles": latest_telem.cycle_counter or 0,
        "timestamp": latest_telem.timestamp.isoformat() if latest_telem.timestamp else None
    })

@app.route('/api/telemetry_history')
@login_required
def api_telemetry_history():
    """Returns recent telemetry logs for the log terminal"""
    # Get robot_id from query parameter or use first accessible robot
    robot_id = request.args.get('robot_id', type=int)
    
    if robot_id:
        if not user_can_access_robot(robot_id):
            return jsonify([])  # Return empty list if no access
        robot = Robot.query.get(robot_id)
    else:
        accessible_ids = get_user_accessible_robots()
        if not accessible_ids:
            return jsonify([])
        robot = Robot.query.get(accessible_ids[0])
    
    if not robot:
        return jsonify([])
    
    # Check if date parameter is provided for historical data
    date_param = request.args.get('date')
    
    if date_param:
        # Parse the date and get data for that specific day
        try:
            target_date = datetime.fromisoformat(date_param).replace(tzinfo=timezone.utc)
            start_of_day = target_date.replace(hour=0, minute=0, second=0, microsecond=0)
            end_of_day = start_of_day + timedelta(days=1)
            
            logs = TelemetryLog.query.filter_by(robot_id=robot.id)\
                .filter(TelemetryLog.timestamp >= start_of_day)\
                .filter(TelemetryLog.timestamp < end_of_day)\
                .order_by(TelemetryLog.timestamp.asc())\
                .all()
        except ValueError:
            return jsonify({"error": "Invalid date format"}), 400
    else:
        # Get last 50 telemetry logs (live mode)
        logs = TelemetryLog.query.filter_by(robot_id=robot.id)\
            .order_by(TelemetryLog.timestamp.desc())\
            .limit(50)\
            .all()
        logs = list(reversed(logs))
    
    log_data = [{
        "timestamp": log.timestamp.isoformat(),
        "battery": log.battery_voltage,
        "temp": log.cpu_temp,
        "load": log.motor_load,
        "status": log.status_code,
        "cycles": log.cycle_counter
    } for log in logs]
    
    return jsonify(log_data)

@app.route('/api/path_history')
@login_required
def api_path_history():
    """Returns path history for trail visualization"""
    # Get robot_id from query parameter or use first accessible robot
    robot_id = request.args.get('robot_id', type=int)
    
    if robot_id:
        if not user_can_access_robot(robot_id):
            return jsonify([])
        robot = Robot.query.get(robot_id)
    else:
        accessible_ids = get_user_accessible_robots()
        if not accessible_ids:
            return jsonify([])
        robot = Robot.query.get(accessible_ids[0])
    
    if not robot:
        return jsonify([])
    
    # Check if date parameter is provided for historical data
    date_param = request.args.get('date')
    since_param = request.args.get('since')  # For incremental updates
    
    if date_param:
        # Parse the date and get data for that specific day
        try:
            target_date = datetime.fromisoformat(date_param).replace(tzinfo=timezone.utc)
            start_of_day = target_date.replace(hour=0, minute=0, second=0, microsecond=0)
            end_of_day = start_of_day + timedelta(days=1)
            
            # Get all path points for that day (sample every 5 minutes to avoid too much data)
            all_paths = PathLog.query.filter_by(robot_id=robot.id)\
                .filter(PathLog.timestamp >= start_of_day)\
                .filter(PathLog.timestamp < end_of_day)\
                .order_by(PathLog.timestamp.asc())\
                .all()
            
            # Sample every 5th point to reduce data size while keeping shape
            paths = [all_paths[i] for i in range(0, len(all_paths), 5)] if len(all_paths) > 200 else all_paths
        except ValueError:
            return jsonify({"error": "Invalid date format"}), 400
    elif since_param:
        # Incremental update: only get new path points since the given timestamp
        try:
            since_time = datetime.fromisoformat(since_param.replace('Z', '+00:00'))
            print(f"[DEBUG] Incremental path query: robot_id={robot.id}, since={since_time}")
            paths = PathLog.query.filter_by(robot_id=robot.id)\
                .filter(PathLog.timestamp > since_time)\
                .order_by(PathLog.timestamp.asc())\
                .all()
            print(f"[DEBUG] Found {len(paths)} new path points")
        except ValueError:
            return jsonify({"error": "Invalid timestamp format"}), 400
    else:
        # Initial load: get all path points for today
        start_of_day = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
        paths = PathLog.query.filter_by(robot_id=robot.id)\
            .filter(PathLog.timestamp >= start_of_day)\
            .order_by(PathLog.timestamp.asc())\
            .all()
    
    path_data = [{
        "x": p.pos_x,
        "y": p.pos_y,
        "timestamp": p.timestamp.isoformat()
    } for p in paths]
    
    return jsonify(path_data)

@app.route('/api/robot/date_range')
@login_required
def api_robot_date_range():
    """Returns the earliest and latest dates with data for a robot"""
    robot_id = request.args.get('robot_id', type=int)
    
    if robot_id:
        if not user_can_access_robot(robot_id):
            return jsonify({"error": "Access denied"}), 403
        robot = Robot.query.get(robot_id)
    else:
        accessible_ids = get_user_accessible_robots()
        if not accessible_ids:
            return jsonify({"error": "No accessible robots"}), 403
        robot = Robot.query.get(accessible_ids[0])
    
    if not robot:
        return jsonify({"error": "Robot not found"}), 404
    
    # Get earliest and latest telemetry timestamps
    earliest_telemetry = TelemetryLog.query.filter_by(robot_id=robot.id)\
        .order_by(TelemetryLog.timestamp.asc()).first()
    latest_telemetry = TelemetryLog.query.filter_by(robot_id=robot.id)\
        .order_by(TelemetryLog.timestamp.desc()).first()
    
    # Get earliest and latest path timestamps
    earliest_path = PathLog.query.filter_by(robot_id=robot.id)\
        .order_by(PathLog.timestamp.asc()).first()
    latest_path = PathLog.query.filter_by(robot_id=robot.id)\
        .order_by(PathLog.timestamp.desc()).first()
    
    # Determine absolute earliest and latest
    earliest = None
    latest = None
    
    if earliest_telemetry and earliest_path:
        earliest = min(earliest_telemetry.timestamp, earliest_path.timestamp)
    elif earliest_telemetry:
        earliest = earliest_telemetry.timestamp
    elif earliest_path:
        earliest = earliest_path.timestamp
    
    if latest_telemetry and latest_path:
        latest = max(latest_telemetry.timestamp, latest_path.timestamp)
    elif latest_telemetry:
        latest = latest_telemetry.timestamp
    elif latest_path:
        latest = latest_path.timestamp
    
    # Make datetimes timezone-aware if they aren't already
    if earliest and earliest.tzinfo is None:
        earliest = earliest.replace(tzinfo=timezone.utc)
    if latest and latest.tzinfo is None:
        latest = latest.replace(tzinfo=timezone.utc)
    
    # Limit to 30 days max history
    if earliest:
        now = datetime.now(timezone.utc)
        max_history_date = now - timedelta(days=30)
        if earliest < max_history_date:
            earliest = max_history_date
    
    result = {
        "earliest_date": earliest.date().isoformat() if earliest else None,
        "latest_date": latest.date().isoformat() if latest else None,
        "earliest_timestamp": earliest.isoformat() if earliest else None,
        "latest_timestamp": latest.isoformat() if latest else None,
        "robot_id": robot.id,
        "serial_number": robot.serial_number
    }
    
    return jsonify(result)

@app.route('/api/telemetry_at_time')
@login_required
def api_telemetry_at_time():
    """Returns telemetry data for a specific date/time"""
    # Get robot_id from query parameter or use first accessible robot
    robot_id = request.args.get('robot_id', type=int)
    
    if robot_id:
        if not user_can_access_robot(robot_id):
            return jsonify({"error": "Access denied"}), 403
        robot = Robot.query.get(robot_id)
    else:
        accessible_ids = get_user_accessible_robots()
        if not accessible_ids:
            return jsonify({"error": "No accessible robots"}), 403
        robot = Robot.query.get(accessible_ids[0])
    
    if not robot:
        return jsonify({"error": "No robot found"}), 404
    
    date_param = request.args.get('date')
    
    if not date_param:
        # Return latest if no date specified
        return api_telemetry()
    
    try:
        target_date = datetime.fromisoformat(date_param).replace(tzinfo=timezone.utc)
        start_of_day = target_date.replace(hour=0, minute=0, second=0, microsecond=0)
        end_of_day = start_of_day + timedelta(days=1)
        
        # Get the last telemetry entry for that day
        latest_telem = TelemetryLog.query.filter_by(robot_id=robot.id)\
            .filter(TelemetryLog.timestamp >= start_of_day)\
            .filter(TelemetryLog.timestamp < end_of_day)\
            .order_by(TelemetryLog.timestamp.desc())\
            .first()
        
        # Get the last position for that day
        latest_path = PathLog.query.filter_by(robot_id=robot.id)\
            .filter(PathLog.timestamp >= start_of_day)\
            .filter(PathLog.timestamp < end_of_day)\
            .order_by(PathLog.timestamp.desc())\
            .first()
        
        if not latest_telem:
            return jsonify({"error": "No data found for this date"}), 404
        
        return jsonify({
            "battery": latest_telem.battery_voltage or 0,
            "cpu_temp": latest_telem.cpu_temp or 0,
            "load": latest_telem.motor_load or 0,
            "status": latest_telem.status_code or "UNKNOWN",
            "pos_x": latest_path.pos_x if latest_path else 50,
            "pos_y": latest_path.pos_y if latest_path else 50,
            "orientation": latest_path.orientation if latest_path else 0,
            "cycles": latest_telem.cycle_counter or 0,
            "timestamp": latest_telem.timestamp.isoformat() if latest_telem.timestamp else None
        })
    except ValueError:
        return jsonify({"error": "Invalid date format"}), 400

@app.route('/api/command', methods=['POST'])
@login_required
def api_command():
    cmd = request.json.get('command')
    # Here you would send UDP/ROS2 message to S3 Controller
    print(f"Command Sent to Robot: {cmd}")
    return jsonify({"status": "success", "msg": f"Command '{cmd}' executed."})

@app.route('/api/health_history')
@login_required
def api_health_history():
    """Returns battery and temperature history for the past 2 hours"""
    # Get robot_id from query parameter or use first accessible robot
    robot_id = request.args.get('robot_id', type=int)
    
    if robot_id:
        if not user_can_access_robot(robot_id):
            return jsonify({"battery": [], "temperature": []})
        robot = Robot.query.get(robot_id)
    else:
        accessible_ids = get_user_accessible_robots()
        if not accessible_ids:
            return jsonify({"battery": [], "temperature": []})
        robot = Robot.query.get(accessible_ids[0])
    
    if not robot:
        return jsonify({"battery": [], "temperature": []})
    
    # Get data from past 2 hours
    two_hours_ago = datetime.now(timezone.utc) - timedelta(hours=2)
    
    # Check if date parameter is provided for historical data
    date_param = request.args.get('date')
    
    if date_param:
        # For historical mode, get 2 hours of data from that day
        try:
            target_date = datetime.fromisoformat(date_param).replace(tzinfo=timezone.utc)
            # Get last 2 hours of the selected day
            end_of_day = target_date.replace(hour=23, minute=59, second=59)
            two_hours_ago = end_of_day - timedelta(hours=2)
            
            logs = TelemetryLog.query.filter_by(robot_id=robot.id)\
                .filter(TelemetryLog.timestamp >= two_hours_ago)\
                .filter(TelemetryLog.timestamp <= end_of_day)\
                .order_by(TelemetryLog.timestamp.asc())\
                .all()
        except ValueError:
            return jsonify({"error": "Invalid date format"}), 400
    else:
        # Live mode - get last 2 hours
        logs = TelemetryLog.query.filter_by(robot_id=robot.id)\
            .filter(TelemetryLog.timestamp >= two_hours_ago)\
            .order_by(TelemetryLog.timestamp.asc())\
            .all()
    
    battery_data = []
    temp_data = []
    
    for log in logs:
        timestamp = log.timestamp.isoformat()
        battery_data.append({
            "time": timestamp,
            "value": log.battery_voltage
        })
        temp_data.append({
            "time": timestamp,
            "value": log.cpu_temp
        })
    
    return jsonify({
        "battery": battery_data,
        "temperature": temp_data
    })

# ==========================================
# ROBOT CLIENT API ENDPOINTS
# ==========================================

# Store pending commands in memory (in production, use Redis or database)
pending_commands = {}

@app.route('/api/robot/telemetry', methods=['POST'])
@login_required
def receive_telemetry():
    """Receive telemetry data from robot client"""
    try:
        data = request.get_json()
        
        robot_id = data.get('robot_id', 1)
        
        # Parse client timestamp if provided, otherwise use server time
        client_timestamp = data.get('timestamp')
        if client_timestamp:
            try:
                timestamp = datetime.fromisoformat(client_timestamp.replace('Z', '+00:00'))
            except (ValueError, AttributeError):
                timestamp = datetime.now(timezone.utc)
        else:
            timestamp = datetime.now(timezone.utc)
        
        # Check if robot exists, if not create it
        robot = Robot.query.get(robot_id)
        if not robot:
            robot = Robot(
                id=robot_id,
                serial_number=f"S4-{robot_id:04d}",
                model_type="32DOF-HUMANOID",
                assigned_to=current_user.id
            )
            db.session.add(robot)
        
        # Create telemetry log with client timestamp
        telemetry = TelemetryLog(
            robot_id=robot_id,
            battery_voltage=data.get('battery_voltage', 24.0),
            cpu_temp=int(data.get('temperature', 45.0)),
            motor_load=data.get('motor_load', 0),
            status_code=data.get('status', 'IDLE'),
            cycle_counter=data.get('cycle_count', 0),
            timestamp=timestamp
        )
        db.session.add(telemetry)
        
        # Create path log with client timestamp
        path = PathLog(
            robot_id=robot_id,
            pos_x=data.get('x', 50.0),
            pos_y=data.get('y', 50.0),
            orientation=data.get('orientation', 0.0),
            timestamp=timestamp
        )
        db.session.add(path)
        
        db.session.commit()
        
        return jsonify({
            'status': 'success',
            'message': 'Telemetry received'
        }), 200
        
    except Exception as e:
        db.session.rollback()
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500

@app.route('/api/robot/commands', methods=['GET'])
@login_required
def get_commands():
    """Send pending commands to robot client"""
    try:
        robot_id = request.args.get('robot_id', 1, type=int)
        
        # Get pending commands for this robot
        commands = pending_commands.get(robot_id, [])
        
        # Clear commands after sending
        if robot_id in pending_commands:
            pending_commands[robot_id] = []
        
        return jsonify(commands), 200
        
    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500

@app.route('/api/robot/command', methods=['POST'])
@login_required
def send_command():
    """Queue a command to be sent to robot client"""
    try:
        data = request.get_json()
        
        robot_id = data.get('robot_id', 1)
        command = data.get('command', '')
        
        # Check if user has access to this robot
        if not user_can_access_robot(robot_id):
            return jsonify({
                'status': 'error',
                'message': 'Access denied to this robot'
            }), 403
        
        # Initialize command queue for robot if doesn't exist
        if robot_id not in pending_commands:
            pending_commands[robot_id] = []
        
        # Add command to queue
        pending_commands[robot_id].append({
            'command': command,
            'timestamp': datetime.now(timezone.utc).isoformat()
        })
        
        return jsonify({
            'status': 'success',
            'message': f'Command "{command}" queued for robot {robot_id}'
        }), 200
        
    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500

@app.route('/api/robots', methods=['GET'])
@login_required
def get_robots():
    """Get list of all robots for current user (or all if admin)"""
    try:
        # Admin can see all robots
        if current_user.username == 'admin':
            robots = Robot.query.all()
        else:
            # Regular users see only their assigned robots
            robots = Robot.query.filter_by(assigned_to=current_user.id).all()
        
        robot_list = []
        for robot in robots:
            # Get latest telemetry
            latest_telemetry = TelemetryLog.query.filter_by(robot_id=robot.id).order_by(TelemetryLog.timestamp.desc()).first()
            
            robot_list.append({
                'id': robot.id,
                'serial_number': robot.serial_number,
                'model_type': robot.model_type,
                'status': latest_telemetry.status_code if latest_telemetry else 'OFFLINE',
                'last_seen': latest_telemetry.timestamp.isoformat() if latest_telemetry else None
            })
        
        return jsonify(robot_list), 200
        
    except Exception as e:
        print(f"Error in get_robots: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500

if __name__ == '__main__':
    # Ensure DB directory exists
    if not os.path.exists('database'):
        os.makedirs('database')
    with app.app_context():
        db.create_all()
    # Get debug and port from environment
    # Get debug and port from environment
    debug_mode = os.getenv('FLASK_DEBUG', 'False').lower() == 'true'
    port = int(os.getenv('PORT', 5001))
    app.run(host='0.0.0.0', port=port, debug=debug_mode)