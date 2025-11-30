from flask import Flask, render_template, request, jsonify, redirect, url_for, session
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from flask_sqlalchemy import SQLAlchemy
from dotenv import load_dotenv
from datetime import datetime, timedelta, timezone
import random, os

# Load environment variables from .env file
load_dotenv()

# Battery voltage to percentage conversion
# For 24V system: Full=25.2V, Empty=20.0V (typical Li-ion 6S configuration)
def battery_voltage_to_percentage(voltage):
    """Convert battery voltage to percentage for 24V system"""
    if voltage is None:
        return 0
    
    BATTERY_MAX = 25.2  # Fully charged 6S Li-ion
    BATTERY_MIN = 22.0  # Empty battery (safe cutoff)
    
    # Clamp voltage to valid range
    voltage = max(BATTERY_MIN, min(BATTERY_MAX, voltage))
    
    # Calculate percentage
    percentage = ((voltage - BATTERY_MIN) / (BATTERY_MAX - BATTERY_MIN)) * 100
    
    return round(percentage, 1)

app = Flask(__name__)
app.secret_key = os.getenv('SECRET_KEY', os.urandom(24).hex())  # Load from environment variable

# Session configuration - 30 minute timeout
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(minutes=30)
app.config['SESSION_COOKIE_SECURE'] = False  # Set to True in production with HTTPS
app.config['SESSION_COOKIE_HTTPONLY'] = True
app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'

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

# --- Software Version Management ---
class SoftwareVersion(db.Model):
    __tablename__ = 'software_versions'
    id = db.Column(db.Integer, primary_key=True)
    controller_name = db.Column(db.String(20), unique=True, nullable=False)  # RCPCU, RCSPM, RCMMC, RCPMU
    version = db.Column(db.String(20), nullable=False)
    release_date = db.Column(db.DateTime, default=datetime.now(timezone.utc))
    release_notes = db.Column(db.Text)
    published_by = db.Column(db.Integer, db.ForeignKey('user.id'))
    is_published = db.Column(db.Boolean, default=False)
    
    # Relationships
    publisher = db.relationship('User', backref=db.backref('published_versions', lazy='dynamic'))

# --- 1. Robot Identity (The "Thing") ---
class Robot(db.Model):
    __tablename__ = 'robots'
    id = db.Column(db.Integer, primary_key=True)
    serial_number = db.Column(db.String(50), unique=True, nullable=False)
    model_type = db.Column(db.String(20), default="32DOF-HUMANOID")
    # Link to the user (Operator)
    assigned_to = db.Column(db.Integer, db.ForeignKey('user.id'))
    
    # Software versions for 4 controllers
    version_rcpcu = db.Column(db.String(20), default="0.0.0")  # Robot Central Processing & Control Unit
    version_rcspm = db.Column(db.String(20), default="0.0.0")  # Robot Control System & Power Management
    version_rcmmc = db.Column(db.String(20), default="0.0.0")  # Robot Control Motion & Motor Controller
    version_rcpmu = db.Column(db.String(20), default="0.0.0")  # Robot Control Power Management Unit
    last_version_check = db.Column(db.DateTime)  # Last time robot checked for updates
    
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

# --- 4. Obstacles/Boundaries (Robot-specific workspace) ---
class Obstacle(db.Model):
    __tablename__ = 'obstacles'
    id = db.Column(db.Integer, primary_key=True)
    robot_id = db.Column(db.Integer, db.ForeignKey('robots.id'), nullable=False)
    
    # Obstacle definition
    name = db.Column(db.String(50), nullable=False)  # e.g., "North Wall", "Conference Table"
    obstacle_type = db.Column(db.String(20), default="rectangle")  # "rectangle", "circle", "polygon"
    
    # Position and size (percentage-based: 0-100)
    x = db.Column(db.Float, nullable=False)
    y = db.Column(db.Float, nullable=False)
    width = db.Column(db.Float)   # For rectangles
    height = db.Column(db.Float)  # For rectangles
    radius = db.Column(db.Float)  # For circles
    
    # SVG path for complex shapes (optional)
    svg_path = db.Column(db.Text)  # SVG path data for irregular shapes
    
    # Visual styling
    color = db.Column(db.String(20), default="rgba(100,100,100,0.4)")
    
    # Relationships
    robot = db.relationship('Robot', backref=db.backref('obstacles', lazy='dynamic'))


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

# --- Helper Functions ---

def format_timestamp(dt):
    """
    Format a datetime object to ISO format with UTC timezone.
    If the datetime is naive (no timezone), assume it's UTC.
    """
    if dt is None:
        return None
    
    # If naive (no timezone info), add UTC timezone
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    
    # Return ISO format string with timezone (e.g., "2025-11-29T14:30:00+00:00")
    return dt.isoformat()

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

@app.before_request
def before_request():
    """Update session activity timestamp on each request"""
    if current_user.is_authenticated:
        session.modified = True  # Reset the session timeout on each request

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
            session.permanent = True  # Enable session timeout
            session.modified = True   # Mark session as modified to reset timeout
            return redirect(url_for('dashboard'))
    return render_template('login.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('index'))

@app.route('/change-password', methods=['GET', 'POST'])
@login_required
def change_password():
    if request.method == 'POST':
        current_password = request.form.get('current_password')
        new_password = request.form.get('new_password')
        confirm_password = request.form.get('confirm_password')
        
        # Verify current password
        if current_user.password != current_password:
            return render_template('change_password.html', error='Current password is incorrect')
        
        # Validate new password
        if len(new_password) < 6:
            return render_template('change_password.html', error='New password must be at least 6 characters')
        
        # Verify password confirmation
        if new_password != confirm_password:
            return render_template('change_password.html', error='New passwords do not match')
        
        # Update password
        current_user.password = new_password
        db.session.commit()
        
        return render_template('change_password.html', success='Password updated successfully!')
    
    return render_template('change_password.html')

@app.route('/software-management')
@login_required
def software_management():
    """Software version management page - Admin only"""
    if current_user.username != 'admin':
        return redirect(url_for('dashboard'))
    
    # Get all software versions
    versions = SoftwareVersion.query.all()
    
    # Get all robots with their current versions
    robots = Robot.query.all()
    
    return render_template('software_management.html', versions=versions, robots=robots)

@app.route('/dashboard')
@login_required
def dashboard():
    return render_template('dashboard.html', name=current_user.username)

@app.route('/api/session/check')
@login_required
def check_session():
    """Check if session is still valid"""
    return jsonify({
        'valid': True,
        'username': current_user.username,
        'user_id': current_user.id
    })

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
        "battery_percent": battery_voltage_to_percentage(latest_telem.battery_voltage),
        "cpu_temp": latest_telem.cpu_temp or 0,
        "load": latest_telem.motor_load or 0,
        "status": latest_telem.status_code or "UNKNOWN",
        "pos_x": latest_path.pos_x if latest_path else 50,
        "pos_y": latest_path.pos_y if latest_path else 50,
        "orientation": latest_path.orientation if latest_path else 0,
        "cycles": latest_telem.cycle_counter or 0,
        "timestamp": format_timestamp(latest_telem.timestamp) if latest_telem.timestamp else None,
        "versions": {
            "RCPCU": robot.version_rcpcu or "0.0.0",
            "RCSPM": robot.version_rcspm or "0.0.0",
            "RCMMC": robot.version_rcmmc or "0.0.0",
            "RCPMU": robot.version_rcpmu or "0.0.0"
        }
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
            # Get timezone offset from client (in minutes, e.g., -300 for EST)
            tz_offset = request.args.get('tz_offset', type=int, default=0)
            
            # Parse date as naive datetime (without timezone)
            target_date = datetime.fromisoformat(date_param)
            
            # This represents midnight in the CLIENT's timezone
            # We need to convert it to UTC for database query
            client_midnight = target_date.replace(hour=0, minute=0, second=0, microsecond=0)
            
            # Convert client's local midnight to UTC
            # tz_offset is in minutes (negative for west of UTC, positive for east)
            utc_offset = timedelta(minutes=-tz_offset)
            start_of_day_utc = client_midnight - utc_offset
            end_of_day_utc = start_of_day_utc + timedelta(days=1)
            
            logs = TelemetryLog.query.filter_by(robot_id=robot.id)\
                .filter(TelemetryLog.timestamp >= start_of_day_utc)\
                .filter(TelemetryLog.timestamp < end_of_day_utc)\
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
        "timestamp": format_timestamp(log.timestamp),
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
            # Get timezone offset from client (in minutes)
            tz_offset = request.args.get('tz_offset', type=int, default=0)
            
            # Parse date as naive datetime
            target_date = datetime.fromisoformat(date_param)
            
            # This represents midnight in the CLIENT's timezone
            client_midnight = target_date.replace(hour=0, minute=0, second=0, microsecond=0)
            
            # Convert client's local midnight to UTC
            utc_offset = timedelta(minutes=-tz_offset)
            start_of_day_utc = client_midnight - utc_offset
            end_of_day_utc = start_of_day_utc + timedelta(days=1)
            
            # Get all path points for that day (sample every 5 minutes to avoid too much data)
            all_paths = PathLog.query.filter_by(robot_id=robot.id)\
                .filter(PathLog.timestamp >= start_of_day_utc)\
                .filter(PathLog.timestamp < end_of_day_utc)\
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
        "timestamp": format_timestamp(p.timestamp)
    } for p in paths]
    
    return jsonify(path_data)

@app.route('/api/obstacles')
@login_required
def api_obstacles():
    """Returns obstacles for a specific robot's workspace"""
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
    
    obstacles = Obstacle.query.filter_by(robot_id=robot.id).all()
    
    obstacle_data = [{
        "id": obs.id,
        "name": obs.name,
        "type": obs.obstacle_type,
        "x": obs.x,
        "y": obs.y,
        "width": obs.width,
        "height": obs.height,
        "radius": obs.radius,
        "svg_path": obs.svg_path,
        "color": obs.color
    } for obs in obstacles]
    
    return jsonify(obstacle_data)

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
        "earliest_timestamp": format_timestamp(earliest) if earliest else None,
        "latest_timestamp": format_timestamp(latest) if latest else None,
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
        # Get timezone offset from client (in minutes)
        tz_offset = request.args.get('tz_offset', type=int, default=0)
        
        # Parse date as naive datetime
        target_date = datetime.fromisoformat(date_param)
        
        # This represents midnight in the CLIENT's timezone
        client_midnight = target_date.replace(hour=0, minute=0, second=0, microsecond=0)
        
        # Convert client's local midnight to UTC
        utc_offset = timedelta(minutes=-tz_offset)
        start_of_day_utc = client_midnight - utc_offset
        end_of_day_utc = start_of_day_utc + timedelta(days=1)
        
        # Get the last telemetry entry for that day
        latest_telem = TelemetryLog.query.filter_by(robot_id=robot.id)\
            .filter(TelemetryLog.timestamp >= start_of_day_utc)\
            .filter(TelemetryLog.timestamp < end_of_day_utc)\
            .order_by(TelemetryLog.timestamp.desc())\
            .first()
        
        # Get the last position for that day
        latest_path = PathLog.query.filter_by(robot_id=robot.id)\
            .filter(PathLog.timestamp >= start_of_day_utc)\
            .filter(PathLog.timestamp < end_of_day_utc)\
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
            "timestamp": format_timestamp(latest_telem.timestamp) if latest_telem.timestamp else None
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
            # Get timezone offset from client (in minutes)
            tz_offset = request.args.get('tz_offset', type=int, default=0)
            
            # Parse date as naive datetime
            target_date = datetime.fromisoformat(date_param)
            
            # Get end of day in client's timezone (23:59:59)
            client_end_of_day = target_date.replace(hour=23, minute=59, second=59, microsecond=999999)
            
            # Convert to UTC
            utc_offset = timedelta(minutes=-tz_offset)
            end_of_day_utc = client_end_of_day - utc_offset
            two_hours_before_utc = end_of_day_utc - timedelta(hours=2)
            
            logs = TelemetryLog.query.filter_by(robot_id=robot.id)\
                .filter(TelemetryLog.timestamp >= two_hours_before_utc)\
                .filter(TelemetryLog.timestamp <= end_of_day_utc)\
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
        timestamp = format_timestamp(log.timestamp)
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
                'last_seen': format_timestamp(latest_telemetry.timestamp) if latest_telemetry else None
            })
        
        return jsonify(robot_list), 200
        
    except Exception as e:
        print(f"Error in get_robots: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': 'Failed to fetch robots'}), 500

@app.route('/api/software/latest_versions', methods=['GET'])
@login_required
def get_latest_software_versions():
    """
    Returns the latest available software versions for all 4 robot controllers
    This endpoint is called by robots during boot sequence and daily at midnight
    """
    # Get published versions from database
    published_versions = SoftwareVersion.query.filter_by(is_published=True).all()
    
    # Build response dictionary
    latest_versions = {}
    release_notes = {}
    latest_date = None
    
    for version in published_versions:
        latest_versions[version.controller_name] = version.version
        release_notes[version.controller_name] = version.release_notes or 'No release notes available'
        
        # Track the most recent release date
        if version.release_date:
            if latest_date is None or version.release_date > latest_date:
                latest_date = version.release_date
    
    # Fallback to default versions if none published
    if not latest_versions:
        latest_versions = {
            'RCPCU': '2.3.1',
            'RCSPM': '1.8.5',
            'RCMMC': '3.1.2',
            'RCPMU': '1.5.9'
        }
        release_notes = {
            'RCPCU': 'Default version',
            'RCSPM': 'Default version',
            'RCMMC': 'Default version',
            'RCPMU': 'Default version'
        }
        latest_date = datetime.now(timezone.utc)
    
    return jsonify({
        **latest_versions,
        'release_date': latest_date.strftime('%Y-%m-%d') if latest_date else None,
        'release_notes': release_notes
    }), 200

@app.route('/api/software/versions', methods=['GET', 'POST'])
@login_required
def manage_software_versions():
    """Get all versions or create/update a version - Admin only"""
    if current_user.username != 'admin':
        return jsonify({'error': 'Admin access required'}), 403
    
    if request.method == 'GET':
        versions = SoftwareVersion.query.all()
        return jsonify([{
            'id': v.id,
            'controller_name': v.controller_name,
            'version': v.version,
            'release_date': format_timestamp(v.release_date),
            'release_notes': v.release_notes,
            'is_published': v.is_published,
            'published_by': v.publisher.username if v.publisher else None
        } for v in versions]), 200
    
    elif request.method == 'POST':
        data = request.json
        controller_name = data.get('controller_name')
        version = data.get('version')
        release_notes = data.get('release_notes', '')
        
        if not controller_name or not version:
            return jsonify({'error': 'controller_name and version are required'}), 400
        
        # Check if version already exists for this controller
        existing = SoftwareVersion.query.filter_by(controller_name=controller_name).first()
        
        if existing:
            # Update existing
            existing.version = version
            existing.release_notes = release_notes
            existing.release_date = datetime.now(timezone.utc)
            existing.published_by = current_user.id
        else:
            # Create new
            new_version = SoftwareVersion(
                controller_name=controller_name,
                version=version,
                release_notes=release_notes,
                published_by=current_user.id,
                is_published=False
            )
            db.session.add(new_version)
        
        db.session.commit()
        return jsonify({'success': True, 'message': 'Version saved'}), 200

@app.route('/api/software/versions/<int:version_id>/publish', methods=['POST'])
@login_required
def publish_software_version(version_id):
    """Publish a software version - Admin only"""
    if current_user.username != 'admin':
        return jsonify({'error': 'Admin access required'}), 403
    
    version = SoftwareVersion.query.get(version_id)
    if not version:
        return jsonify({'error': 'Version not found'}), 404
    
    version.is_published = True
    version.release_date = datetime.now(timezone.utc)
    version.published_by = current_user.id
    
    db.session.commit()
    
    return jsonify({
        'success': True,
        'message': f'{version.controller_name} version {version.version} published successfully'
    }), 200

@app.route('/api/software/versions/<int:version_id>/unpublish', methods=['POST'])
@login_required
def unpublish_software_version(version_id):
    """Unpublish a software version - Admin only"""
    if current_user.username != 'admin':
        return jsonify({'error': 'Admin access required'}), 403
    
    version = SoftwareVersion.query.get(version_id)
    if not version:
        return jsonify({'error': 'Version not found'}), 404
    
    version.is_published = False
    db.session.commit()
    
    return jsonify({
        'success': True,
        'message': f'{version.controller_name} version {version.version} unpublished'
    }), 200

@app.route('/api/software/versions/<int:version_id>', methods=['DELETE'])
@login_required
def delete_software_version(version_id):
    """Delete a software version - Admin only"""
    if current_user.username != 'admin':
        return jsonify({'error': 'Admin access required'}), 403
    
    version = SoftwareVersion.query.get(version_id)
    if not version:
        return jsonify({'error': 'Version not found'}), 404
    
    db.session.delete(version)
    db.session.commit()
    
    return jsonify({
        'success': True,
        'message': f'{version.controller_name} version deleted'
    }), 200

@app.route('/api/robot/version', methods=['POST'])
@login_required
def update_robot_versions():
    """
    Update robot's software versions in database
    Called by robot client when sending version information
    """
    try:
        data = request.json
        robot_id = data.get('robot_id')
        
        if not robot_id:
            return jsonify({'error': 'robot_id required'}), 400
        
        # Check access permission
        if not user_can_access_robot(robot_id):
            return jsonify({'error': 'Access denied'}), 403
        
        robot = Robot.query.get(robot_id)
        if not robot:
            return jsonify({'error': 'Robot not found'}), 404
        
        # Update versions if provided
        if 'version_rcpcu' in data:
            robot.version_rcpcu = data['version_rcpcu']
        if 'version_rcspm' in data:
            robot.version_rcspm = data['version_rcspm']
        if 'version_rcmmc' in data:
            robot.version_rcmmc = data['version_rcmmc']
        if 'version_rcpmu' in data:
            robot.version_rcpmu = data['version_rcpmu']
        
        # Update last version check timestamp
        robot.last_version_check = datetime.now(timezone.utc)
        
        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': 'Version information updated',
            'versions': {
                'RCPCU': robot.version_rcpcu,
                'RCSPM': robot.version_rcspm,
                'RCMMC': robot.version_rcmmc,
                'RCPMU': robot.version_rcpmu
            }
        }), 200
        
    except Exception as e:
        print(f"Error updating robot versions: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': 'Failed to update versions'}), 500
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