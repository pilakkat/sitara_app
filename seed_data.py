from app import app, db, Robot, TelemetryLog, PathLog
import random
import math

from datetime import datetime, timedelta, timezone

# --- CONFIGURATION ---
ROBOT_SERIAL = "SITARA-X1"
HOURS_TO_GENERATE = 24
TELEMETRY_INTERVAL_MINS = 5  # Log health every 5 mins
PATH_INTERVAL_MINS = 1       # Log movement every 1 min

def generate_synthetic_data():
    print(f"--- SEEDING DATA FOR {ROBOT_SERIAL} ---")
    
    with app.app_context():
        # 1. Ensure Robot Exists
        robot = Robot.query.filter_by(serial_number=ROBOT_SERIAL).first()
        if not robot:
            robot = Robot(serial_number=ROBOT_SERIAL, model_type="32DOF-HUMANOID")
            db.session.add(robot)
            db.session.commit()
            print(f"Created new robot: {ROBOT_SERIAL}")
        else:
            print(f"Found existing robot: {ROBOT_SERIAL}")

        # 2. Clear old data for a fresh start (Optional)
        # TelemetryLog.query.filter_by(robot_id=robot.id).delete()
        # PathLog.query.filter_by(robot_id=robot.id).delete()

        end_time = datetime.now(timezone.utc)
        start_time = end_time - timedelta(hours=HOURS_TO_GENERATE)
        
        telemetry_buffer = []
        path_buffer = []
        
        # simulated values
        current_battery = 24.8
        cycle_count = 12000
        
        # Loop through time minute by minute
        total_minutes = HOURS_TO_GENERATE * 60
        
        for i in range(total_minutes):
            current_step_time = start_time + timedelta(minutes=i)
            
            # --- MATH FOR MOVEMENT (Lissajous Figure / Figure-8) ---
            # This makes the robot look like it's patrolling in a pattern
            t = i * 0.05
            pos_x = 50 + (30 * math.sin(t))       # Center 50, radius 30
            pos_y = 50 + (20 * math.sin(2 * t))   # Figure-8 shape
            orientation = (math.degrees(math.atan2(math.cos(2*t), math.cos(t))) + 360) % 360

            # --- MATH FOR BATTERY (Drain and Recharge) ---
            # Drain 0.05V per minute, recharge if drops below 21V
            if current_battery > 21.0:
                current_battery -= random.uniform(0.01, 0.03)
            else:
                current_battery = 25.2 # Instant recharge (swapped battery)
            
            # --- GENERATE PATH LOG (High Frequency) ---
            if i % PATH_INTERVAL_MINS == 0:
                path = PathLog(
                    robot_id=robot.id,
                    timestamp=current_step_time,
                    pos_x=round(pos_x, 2),
                    pos_y=round(pos_y, 2),
                    orientation=round(orientation, 1)
                )
                path_buffer.append(path)

            # --- GENERATE TELEMETRY LOG (Lower Frequency) ---
            if i % TELEMETRY_INTERVAL_MINS == 0:
                # Add some noise to temperature
                temp = 45 + (10 * math.sin(t/10)) + random.uniform(-2, 2)
                
                # Random status hiccups
                status = "NOMINAL"
                if temp > 58: status = "HIGH_TEMP_WARN"
                if random.random() > 0.98: status = "CALIBRATING_SENSORS"

                log = TelemetryLog(
                    robot_id=robot.id,
                    timestamp=current_step_time,
                    battery_voltage=round(current_battery, 2),
                    cpu_temp=int(temp),
                    motor_load=random.randint(20, 60),
                    cycle_counter=cycle_count + (i * 60),
                    status_code=status
                )
                telemetry_buffer.append(log)

        # Bulk Save
        print(f"Generating {len(path_buffer)} path points...")
        db.session.add_all(path_buffer)
        
        print(f"Generating {len(telemetry_buffer)} telemetry logs...")
        db.session.add_all(telemetry_buffer)
        
        db.session.commit()
        print("--- SEEDING COMPLETE ---")

if __name__ == "__main__":
    generate_synthetic_data()