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

# --- Mock Data Generator (Simulating Robot S1/S2 Streams) ---
def get_robot_telemetry():
    # Simulating data from the 32 DOF Humanoid
    return {
        "battery": round(random.uniform(20.5, 25.2), 1), # Volts (24V arch)
        "cpu_temp": random.randint(45, 65),              # Celsius
        "status": "OPERATIONAL" if random.random() > 0.1 else "CALIBRATING",
        "load": random.randint(10, 85),                  # Motor Load %
        "pos_x": random.randint(10, 90),                 # Map % coordinates
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

# --- APIs (AJAX Hooks) ---

@app.route('/api/telemetry')
@login_required
def api_telemetry():
    data = get_robot_telemetry()
    return jsonify(data)

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