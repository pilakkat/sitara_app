from flask import Flask, render_template, request, jsonify, redirect, url_for
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from flask_sqlalchemy import SQLAlchemy
from dotenv import load_dotenv
import random, datetime, os

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

class Telemetry(db.Model):
    """Stores robot telemetry snapshots coming from hardware layer.
    Add records via /api/telemetry/ingest (POST) or another ingestion pipeline.
    """
    id = db.Column(db.Integer, primary_key=True)
    battery = db.Column(db.Float)          # Voltage
    cpu_temp = db.Column(db.Integer)       # Celsius
    status = db.Column(db.String(32))      # OPERATIONAL / CALIBRATING / etc
    load = db.Column(db.Integer)           # Motor load %
    pos_x = db.Column(db.Integer)          # Map X coordinate (0-100)
    pos_y = db.Column(db.Integer)          # Map Y coordinate (0-100)
    timestamp = db.Column(db.DateTime, default=datetime.datetime.utcnow, index=True)

# --- Mock Data Generator (Simulating Robot S1/S2 Streams) ---
def get_robot_telemetry_fallback():
    """Fallback generator retained only for initial empty DB state.
    Once real telemetry ingestion is active, this should rarely be used.
    """
    return {
        "battery": None,  # Intentionally None so UI shows N/A until real data arrives
        "cpu_temp": random.randint(45, 65),
        "status": "OPERATIONAL" if random.random() > 0.1 else "CALIBRATING",
        "load": random.randint(10, 85),
        "pos_x": random.randint(10, 90),
        "pos_y": random.randint(10, 90)
    }

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
    """Return latest telemetry snapshot from DB. Battery (and all fields) come from stored data.
    If DB empty, provide fallback with battery None instead of random demo value.
    """
    latest = Telemetry.query.order_by(Telemetry.timestamp.desc()).first()
    if latest:
        data = {
            "battery": latest.battery,
            "cpu_temp": latest.cpu_temp,
            "status": latest.status,
            "load": latest.load,
            "pos_x": latest.pos_x,
            "pos_y": latest.pos_y
        }
    else:
        data = get_robot_telemetry_fallback()
    return jsonify(data)

@app.route('/api/telemetry/ingest', methods=['POST'])
def api_ingest_telemetry():
    """Ingest telemetry posted from robot controller or bridge process.
    Expected JSON: {battery, cpu_temp, status, load, pos_x, pos_y}
    Returns stored record id. (No auth here for simplicity; add auth/token in production.)
    """
    payload = request.json or {}
    t = Telemetry(
        battery=payload.get('battery'),
        cpu_temp=payload.get('cpu_temp'),
        status=payload.get('status'),
        load=payload.get('load'),
        pos_x=payload.get('pos_x'),
        pos_y=payload.get('pos_y')
    )
    db.session.add(t)
    db.session.commit()
    return jsonify({"status": "stored", "id": t.id})

@app.route('/api/command', methods=['POST'])
@login_required
def api_command():
    cmd = request.json.get('command')
    # Here you would send UDP/ROS2 message to S3 Controller
    print(f"Command Sent to Robot: {cmd}")
    return jsonify({"status": "success", "msg": f"Command '{cmd}' executed."})

@app.route('/admin/seed-telemetry')
def admin_seed_telemetry():
    """Create one demo telemetry record if none exist. Returns the latest record.
    (No auth for simplicity; add protection in production.)
    """
    latest = Telemetry.query.order_by(Telemetry.timestamp.desc()).first()
    if not latest:
        t = Telemetry(
            battery=24.0,
            cpu_temp=50,
            status='OPERATIONAL',
            load=35,
            pos_x=50,
            pos_y=50
        )
        db.session.add(t)
        db.session.commit()
        latest = t
    return jsonify({
        'id': latest.id,
        'battery': latest.battery,
        'cpu_temp': latest.cpu_temp,
        'status': latest.status,
        'load': latest.load,
        'pos_x': latest.pos_x,
        'pos_y': latest.pos_y,
        'timestamp': latest.timestamp.isoformat()
    })

if __name__ == '__main__':
    # Ensure DB directory exists
    if not os.path.exists('database'):
        os.makedirs('database')
    with app.app_context():
        db.create_all()
        # Auto-seed a baseline telemetry entry if empty so dashboard isn't blank
        if Telemetry.query.count() == 0:
            seed = Telemetry(
                battery=24.2,
                cpu_temp=52,
                status='CALIBRATING',
                load=30,
                pos_x=48,
                pos_y=55
            )
            db.session.add(seed)
            db.session.commit()
    # Get debug and port from environment
    debug_mode = os.getenv('FLASK_DEBUG', 'False').lower() == 'true'
    port = int(os.getenv('PORT', 5001))
    app.run(host='0.0.0.0', port=port, debug=debug_mode)