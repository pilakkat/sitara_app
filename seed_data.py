from app import app, db, Robot, TelemetryLog, PathLog
import random
import math

from datetime import datetime, timedelta, timezone

# --- CONFIGURATION ---
ROBOT_SERIAL = "SITARA-X1"
DAYS_TO_GENERATE = 7  # One week of data
TELEMETRY_INTERVAL_MINS = 5  # Log health every 5 mins
PATH_INTERVAL_MINS = 1       # Log movement every 1 min
TELEMETRY_CHANGE_THRESHOLD = {
    'battery': 0.1,      # Log if battery changes by more than 0.1V
    'temp': 2,           # Log if temp changes by more than 2°C
    'load': 5            # Log if load changes by more than 5%
}

def generate_synthetic_data():
    print(f"--- SEEDING DATA FOR {ROBOT_SERIAL} (Last {DAYS_TO_GENERATE} days) ---")
    
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

        # 2. Clear old data for a fresh start
        print("Clearing old data...")
        TelemetryLog.query.filter_by(robot_id=robot.id).delete()
        PathLog.query.filter_by(robot_id=robot.id).delete()
        db.session.commit()

        end_time = datetime.now(timezone.utc)
        start_time = end_time - timedelta(days=DAYS_TO_GENERATE)
        
        telemetry_buffer = []
        path_buffer = []
        
        # Simulated values
        current_battery = 24.8
        cycle_count = 12000
        
        # Track last logged telemetry values for change detection
        last_logged_battery = current_battery
        last_logged_temp = 45
        last_logged_load = 30
        last_logged_status = "NOMINAL"
        last_telemetry_time = start_time
        
        # Track last position for smooth movement
        last_pos_x = 50.0
        last_pos_y = 50.0
        last_orientation = 0.0
        
        # Movement state
        movement_phase = 0  # Different patrol patterns
        idle_until = None   # Track when robot is idle/stationary
        
        # Loop through time minute by minute
        total_minutes = DAYS_TO_GENERATE * 24 * 60
        print(f"Generating {total_minutes} minutes of data...")
        
        for i in range(total_minutes):
            current_step_time = start_time + timedelta(minutes=i)
            
            # --- SIMULATE DAY/NIGHT CYCLES (Robot rests at night) ---
            hour_of_day = current_step_time.hour
            is_night = hour_of_day < 6 or hour_of_day >= 22  # 10 PM to 6 AM
            
            # Simulate occasional maintenance/idle periods during the day
            if idle_until is None and not is_night and random.random() < 0.001:  # 0.1% chance per minute
                idle_until = current_step_time + timedelta(minutes=random.randint(15, 60))
                print(f"Robot entering maintenance mode at {current_step_time.strftime('%Y-%m-%d %H:%M')}")
            
            is_idle = (idle_until and current_step_time < idle_until) or is_night
            
            if idle_until and current_step_time >= idle_until:
                idle_until = None  # Resume operations
            
            # --- REALISTIC MOVEMENT PATTERNS ---
            if not is_idle:
                # Active movement - use smooth patrol patterns
                # Change patrol pattern every few hours
                if i % (180) == 0:  # Every 3 hours
                    movement_phase = random.randint(0, 3)
                
                t = i * 0.02  # Slower movement for realism
                
                if movement_phase == 0:
                    # Figure-8 pattern
                    target_x = 50 + (30 * math.sin(t))
                    target_y = 50 + (20 * math.sin(2 * t))
                elif movement_phase == 1:
                    # Circular patrol
                    target_x = 50 + (35 * math.cos(t))
                    target_y = 50 + (35 * math.sin(t))
                elif movement_phase == 2:
                    # Square patrol
                    phase = (t % (2 * math.pi)) / (2 * math.pi)
                    if phase < 0.25:
                        target_x = 20 + (phase * 4 * 60)
                        target_y = 20
                    elif phase < 0.5:
                        target_x = 80
                        target_y = 20 + ((phase - 0.25) * 4 * 60)
                    elif phase < 0.75:
                        target_x = 80 - ((phase - 0.5) * 4 * 60)
                        target_y = 80
                    else:
                        target_x = 20
                        target_y = 80 - ((phase - 0.75) * 4 * 60)
                else:
                    # Random walk with smooth transitions
                    target_x = 50 + (25 * math.sin(t)) + (10 * math.cos(t * 3))
                    target_y = 50 + (25 * math.cos(t)) + (10 * math.sin(t * 2.5))
                
                # Smooth interpolation to avoid teleportation (max speed limit)
                max_speed = 2.0  # Maximum units per minute
                dx = target_x - last_pos_x
                dy = target_y - last_pos_y
                distance = math.sqrt(dx*dx + dy*dy)
                
                if distance > max_speed:
                    # Limit speed
                    ratio = max_speed / distance
                    pos_x = last_pos_x + (dx * ratio)
                    pos_y = last_pos_y + (dy * ratio)
                else:
                    pos_x = target_x
                    pos_y = target_y
                
                # Calculate orientation based on movement direction
                if abs(dx) > 0.1 or abs(dy) > 0.1:
                    orientation = (math.degrees(math.atan2(dy, dx)) + 90) % 360
                else:
                    orientation = last_orientation  # Keep last orientation if not moving
                    
            else:
                # Idle/Night - stay at charging station
                pos_x = last_pos_x  # Stay at last position
                pos_y = last_pos_y
                orientation = last_orientation
            
            # Keep positions in bounds (0-100)
            pos_x = max(5, min(95, pos_x))
            pos_y = max(5, min(95, pos_y))
            
            # Update last position
            last_pos_x = pos_x
            last_pos_y = pos_y
            last_orientation = orientation

            # --- GENERATE PATH LOG (Every Minute) ---
            if i % PATH_INTERVAL_MINS == 0:
                path = PathLog(
                    robot_id=robot.id,
                    timestamp=current_step_time,
                    pos_x=round(pos_x, 2),
                    pos_y=round(pos_y, 2),
                    orientation=round(orientation, 1)
                )
                path_buffer.append(path)

            # --- BATTERY MANAGEMENT ---
            if is_idle:
                # Charging at night or during maintenance
                if current_battery < 25.0:
                    current_battery = min(25.2, current_battery + 0.05)  # Charge slowly
            else:
                # Active - drain battery
                drain_rate = random.uniform(0.008, 0.015)
                current_battery -= drain_rate
                
                # Emergency recharge if too low
                if current_battery < 20.5:
                    current_battery = 25.2  # Simulate battery swap
                    print(f"Battery swap at {current_step_time.strftime('%Y-%m-%d %H:%M')}")

            # --- TELEMETRY GENERATION (Every 5 Minutes) ---
            if i % TELEMETRY_INTERVAL_MINS == 0:
                # Temperature varies with activity
                base_temp = 40 if is_idle else 48
                temp_variation = 3 if is_idle else 12
                temp = base_temp + (temp_variation * math.sin(i * 0.01)) + random.uniform(-2, 2)
                temp = max(35, min(65, int(temp)))  # Keep in reasonable range
                
                # Motor load based on activity
                if is_idle:
                    motor_load = random.randint(5, 15)  # Low load when idle
                else:
                    motor_load = random.randint(25, 65)  # Higher when active
                
                # Status logic
                status = "NOMINAL"
                if is_idle and is_night:
                    status = "CHARGING"
                elif is_idle:
                    status = "MAINTENANCE_MODE"
                elif temp > 58:
                    status = "HIGH_TEMP_WARN"
                elif current_battery < 21.5:
                    status = "LOW_BATTERY_WARN"
                elif random.random() > 0.985:  # Occasional sensor calibration
                    status = "CALIBRATING_SENSORS"
                
                # --- INTELLIGENT LOGGING: Only log if values changed significantly ---
                should_log = False
                time_since_last = (current_step_time - last_telemetry_time).total_seconds() / 60
                
                # Force log every hour as keepalive
                if time_since_last >= 60:
                    should_log = True
                # Log if significant changes detected
                elif (abs(current_battery - last_logged_battery) >= TELEMETRY_CHANGE_THRESHOLD['battery'] or
                      abs(temp - last_logged_temp) >= TELEMETRY_CHANGE_THRESHOLD['temp'] or
                      abs(motor_load - last_logged_load) >= TELEMETRY_CHANGE_THRESHOLD['load'] or
                      status != last_logged_status):
                    should_log = True
                
                if should_log:
                    log = TelemetryLog(
                        robot_id=robot.id,
                        timestamp=current_step_time,
                        battery_voltage=round(current_battery, 2),
                        cpu_temp=temp,
                        motor_load=motor_load,
                        cycle_counter=cycle_count + (i * 60),
                        status_code=status
                    )
                    telemetry_buffer.append(log)
                    
                    # Update last logged values
                    last_logged_battery = current_battery
                    last_logged_temp = temp
                    last_logged_load = motor_load
                    last_logged_status = status
                    last_telemetry_time = current_step_time
            
            # Bulk commit every 1000 records to avoid memory issues
            if len(path_buffer) >= 5000:
                db.session.add_all(path_buffer)
                db.session.commit()
                print(f"  Saved {len(path_buffer)} path points... ({i}/{total_minutes} minutes processed)")
                path_buffer = []
            
            if len(telemetry_buffer) >= 1000:
                db.session.add_all(telemetry_buffer)
                db.session.commit()
                print(f"  Saved {len(telemetry_buffer)} telemetry logs...")
                telemetry_buffer = []

        # Final bulk save
        if path_buffer:
            print(f"Saving final {len(path_buffer)} path points...")
            db.session.add_all(path_buffer)
        
        if telemetry_buffer:
            print(f"Saving final {len(telemetry_buffer)} telemetry logs...")
            db.session.add_all(telemetry_buffer)
        
        db.session.commit()
        
        # Summary
        total_paths = PathLog.query.filter_by(robot_id=robot.id).count()
        total_telemetry = TelemetryLog.query.filter_by(robot_id=robot.id).count()
        
        print("--- SEEDING COMPLETE ---")
        print(f"Total Path Logs: {total_paths}")
        print(f"Total Telemetry Logs: {total_telemetry}")
        print(f"Time Range: {start_time.strftime('%Y-%m-%d %H:%M')} to {end_time.strftime('%Y-%m-%d %H:%M')}")

if __name__ == "__main__":
    generate_synthetic_data()