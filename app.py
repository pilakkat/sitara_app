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
    current_time = datetime.utcnow()

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
    new_path = PathLog(
        robot_id=robot.id,
        pos_x=data['pos_x'],
        pos_y=data['pos_y'],
        timestamp=current_time
    )
    db.session.add(new_path)
    
    db.session.commit()
    return jsonify({"msg": "Synced"}), 200

def cleanup_old_data():
    """Deletes logs older than 7 days"""
    expiration_date = datetime.utcnow() - timedelta(days=7)
    
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
    # Get the default robot (you can modify this to support multiple robots)
    robot = Robot.query.first()
    
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

@app.route('/api/path_history')
@login_required
def api_path_history():
    """Returns recent path history for trail visualization"""
    robot = Robot.query.first()
    
    if not robot:
        return jsonify([])
    
    # Get last 100 path points
    recent_paths = PathLog.query.filter_by(robot_id=robot.id)\
        .order_by(PathLog.timestamp.desc())\
        .limit(100)\
        .all()
    
    path_data = [{
        "x": p.pos_x,
        "y": p.pos_y,
        "timestamp": p.timestamp.isoformat()
    } for p in reversed(recent_paths)]
    
    return jsonify(path_data)

@app.route('/api/telemetry_history')
@login_required
def api_telemetry_history():
    """Returns recent telemetry logs for the log terminal"""
    robot = Robot.query.first()
    
    if not robot:
        return jsonify([])
    
    # Get last 50 telemetry logs
    recent_logs = TelemetryLog.query.filter_by(robot_id=robot.id)\
        .order_by(TelemetryLog.timestamp.desc())\
        .limit(50)\
        .all()
    
    log_data = [{
        "timestamp": log.timestamp.isoformat(),
        "battery": log.battery_voltage,
        "temp": log.cpu_temp,
        "load": log.motor_load,
        "status": log.status_code,
        "cycles": log.cycle_counter
    } for log in reversed(recent_logs)]
    
    return jsonify(log_data)

@app.route('/api/command', methods=['POST'])
@login_required
def api_command():
    cmd = request.json.get('command')
    # Here you would send UDP/ROS2 message to S3 Controller
    print(f"Command Sent to Robot: {cmd}")
    return jsonify({"status": "success", "msg": f"Command '{cmd}' executed."})

if __name__ == '__main__':
    # Ensure DB directory exists
    if not os.path.exists('database'):
        os.makedirs('database')
    with app.app_context():
        db.create_all()
    # Get debug and port from environment
    debug_mode = os.getenv('FLASK_DEBUG', 'False').lower() == 'true'
    port = int(os.getenv('PORT', 5001))
    app.run(host='0.0.0.0', port=port, debug=debug_mode)