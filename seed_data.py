from app import app, db, Robot, TelemetryLog, PathLog, User, Obstacle
import random
import math

from datetime import datetime, timedelta, timezone

# --- OBSTACLE DEFINITIONS (Templates for each workspace) ---
# Different robots can have different workspaces
WORKSPACE_OBSTACLES = {
    'office_floor_1': [
        # Walls (5% thick)
        {'name': 'North Wall', 'type': 'rectangle', 'x': 0, 'y': 0, 'width': 100, 'height': 5, 'color': 'rgba(80,80,80,0.5)'},
        {'name': 'South Wall', 'type': 'rectangle', 'x': 0, 'y': 95, 'width': 100, 'height': 5, 'color': 'rgba(80,80,80,0.5)'},
        {'name': 'West Wall', 'type': 'rectangle', 'x': 0, 'y': 0, 'width': 5, 'height': 100, 'color': 'rgba(80,80,80,0.5)'},
        {'name': 'East Wall', 'type': 'rectangle', 'x': 95, 'y': 0, 'width': 5, 'height': 100, 'color': 'rgba(80,80,80,0.5)'},
        
        # Furniture
        {'name': 'Conference Table', 'type': 'rectangle', 'x': 15, 'y': 35, 'width': 25, 'height': 30, 'color': 'rgba(139,90,43,0.5)'},
        {'name': 'Desk', 'type': 'rectangle', 'x': 70, 'y': 10, 'width': 20, 'height': 15, 'color': 'rgba(120,80,50,0.5)'},
        {'name': 'Chair', 'type': 'circle', 'x': 79, 'y': 31, 'radius': 4, 'color': 'rgba(100,100,100,0.4)'},
        {'name': 'Storage Cabinet', 'type': 'rectangle', 'x': 70, 'y': 75, 'width': 20, 'height': 18, 'color': 'rgba(90,90,90,0.5)'},
        {'name': 'Pillar', 'type': 'circle', 'x': 59, 'y': 52, 'radius': 4, 'color': 'rgba(150,150,150,0.6)'}
    ],
    'warehouse_zone_a': [
        # Walls
        {'name': 'North Wall', 'type': 'rectangle', 'x': 0, 'y': 0, 'width': 100, 'height': 5, 'color': 'rgba(80,80,80,0.5)'},
        {'name': 'South Wall', 'type': 'rectangle', 'x': 0, 'y': 95, 'width': 100, 'height': 5, 'color': 'rgba(80,80,80,0.5)'},
        {'name': 'West Wall', 'type': 'rectangle', 'x': 0, 'y': 0, 'width': 5, 'height': 100, 'color': 'rgba(80,80,80,0.5)'},
        {'name': 'East Wall', 'type': 'rectangle', 'x': 95, 'y': 0, 'width': 5, 'height': 100, 'color': 'rgba(80,80,80,0.5)'},
        
        # Warehouse obstacles
        {'name': 'Rack 1', 'type': 'rectangle', 'x': 10, 'y': 20, 'width': 15, 'height': 40, 'color': 'rgba(180,120,60,0.5)'},
        {'name': 'Rack 2', 'type': 'rectangle', 'x': 35, 'y': 20, 'width': 15, 'height': 40, 'color': 'rgba(180,120,60,0.5)'},
        {'name': 'Rack 3', 'type': 'rectangle', 'x': 60, 'y': 20, 'width': 15, 'height': 40, 'color': 'rgba(180,120,60,0.5)'},
        {'name': 'Loading Dock', 'type': 'rectangle', 'x': 35, 'y': 70, 'width': 30, 'height': 20, 'color': 'rgba(100,150,200,0.4)'}
    ],
    'lab_environment': [
        # Walls
        {'name': 'North Wall', 'type': 'rectangle', 'x': 0, 'y': 0, 'width': 100, 'height': 5, 'color': 'rgba(80,80,80,0.5)'},
        {'name': 'South Wall', 'type': 'rectangle', 'x': 0, 'y': 95, 'width': 100, 'height': 5, 'color': 'rgba(80,80,80,0.5)'},
        {'name': 'West Wall', 'type': 'rectangle', 'x': 0, 'y': 0, 'width': 5, 'height': 100, 'color': 'rgba(80,80,80,0.5)'},
        {'name': 'East Wall', 'type': 'rectangle', 'x': 95, 'y': 0, 'width': 5, 'height': 100, 'color': 'rgba(80,80,80,0.5)'},
        
        # Lab equipment
        {'name': 'Lab Bench 1', 'type': 'rectangle', 'x': 10, 'y': 10, 'width': 35, 'height': 12, 'color': 'rgba(200,200,200,0.5)'},
        {'name': 'Lab Bench 2', 'type': 'rectangle', 'x': 10, 'y': 30, 'width': 35, 'height': 12, 'color': 'rgba(200,200,200,0.5)'},
        {'name': 'Equipment Cabinet', 'type': 'rectangle', 'x': 55, 'y': 10, 'width': 30, 'height': 20, 'color': 'rgba(150,150,150,0.5)'},
        {'name': 'Safety Zone', 'type': 'rectangle', 'x': 60, 'y': 70, 'width': 25, 'height': 20, 'color': 'rgba(255,200,0,0.3)'}
    ]
}

# Map robot serials to their workspace environments
ROBOT_WORKSPACES = {
    'SITARA32DOFH0001': 'office_floor_1',
    'SITARA32DOFH0002': 'warehouse_zone_a',
    'SITARA32DOFH0003': 'lab_environment'
}

def get_obstacles_for_workspace(workspace_name):
    """Get obstacle definitions for a specific workspace"""
    return WORKSPACE_OBSTACLES.get(workspace_name, WORKSPACE_OBSTACLES['office_floor_1'])

def check_collision(x, y, obstacles, buffer=2):
    """Check if position collides with any obstacle"""
    for obstacle in obstacles:
        obs_type = obstacle.get('type', 'rectangle')
        
        if obs_type == 'rectangle':
            if (x >= (obstacle['x'] - buffer) and 
                x <= (obstacle['x'] + obstacle['width'] + buffer) and
                y >= (obstacle['y'] - buffer) and 
                y <= (obstacle['y'] + obstacle['height'] + buffer)):
                return True
        elif obs_type == 'circle':
            # Check distance from circle center
            center_x = obstacle['x']
            center_y = obstacle['y']
            radius = obstacle['radius'] + buffer
            dist = math.sqrt((x - center_x)**2 + (y - center_y)**2)
            if dist <= radius:
                return True
    return False

def is_valid_position(x, y, obstacles):
    """Check if position is valid (within bounds and no collision)"""
    # Keep robot within safe area (away from edges)
    if x < 5 or x > 95 or y < 5 or y > 95:
        return False
    # Check obstacle collision
    return not check_collision(x, y, obstacles)

def find_valid_position_near(x, y, obstacles, max_attempts=20):
    """Find a valid position near the target coordinates"""
    if is_valid_position(x, y, obstacles):
        return x, y
    
    # Try positions in expanding radius
    for radius in range(3, 16, 2):
        for angle in range(0, 360, 45):
            rad = math.radians(angle)
            test_x = x + radius * math.cos(rad)
            test_y = y + radius * math.sin(rad)
            
            if is_valid_position(test_x, test_y, obstacles):
                return test_x, test_y
    
    # Fallback to center
    return 50.0, 50.0

# --- CONFIGURATION ---
ROBOTS = [
    {
        'serial': 'SITARA32DOFH0001',
        'operator': 'deepak',
        'days': 10
    },
    {
        'serial': 'SITARA32DOFH0002',
        'operator': 'lithin',  # operator2 username
        'days': 6
    },
    {
        'serial': 'SITARA32DOFH0003',
        'operator': 'khaleel',  # operator3 username
        'days': 2
    }
]
TELEMETRY_INTERVAL_MINS = 5  # Log health every 5 mins
PATH_INTERVAL_MINS = 1       # Log movement every 1 min
TELEMETRY_CHANGE_THRESHOLD = {
    'battery': 0.1,      # Log if battery changes by more than 0.1V
    'temp': 2,           # Log if temp changes by more than 2°C
    'load': 5            # Log if load changes by more than 5%
}

def generate_synthetic_data_for_robot(robot_serial, operator_username, days_to_generate):
    """Generate synthetic data for a single robot"""
    print(f"--- SEEDING DATA FOR {robot_serial} (Last {days_to_generate} days, assigned to {operator_username}) ---")
    
    with app.app_context():
        # 0. Get operator user for robot assignment
        operator_user = User.query.filter_by(username=operator_username).first()
        if not operator_user:
            print(f"WARNING: Operator user '{operator_username}' not found. Please run init_db.py first!")
            return
        
        # 1. Ensure Robot Exists and is assigned to operator
        robot = Robot.query.filter_by(serial_number=robot_serial).first()
        if not robot:
            robot = Robot(
                serial_number=robot_serial, 
                model_type="32DOF-HUMANOID",
                assigned_to=operator_user.id
            )
            db.session.add(robot)
            db.session.commit()
            print(f"Created new robot: {robot_serial} (assigned to operator '{operator_username}')")
        else:
            # Update assignment to operator if different
            if robot.assigned_to != operator_user.id:
                robot.assigned_to = operator_user.id
                db.session.commit()
                print(f"Updated robot assignment: {robot_serial} (now assigned to operator '{operator_username}')")
            else:
                print(f"Found existing robot: {robot_serial} (assigned to operator '{operator_username}')")

        # 2. Clear old data for a fresh start
        print("Clearing old data...")
        TelemetryLog.query.filter_by(robot_id=robot.id).delete()
        PathLog.query.filter_by(robot_id=robot.id).delete()
        Obstacle.query.filter_by(robot_id=robot.id).delete()
        db.session.commit()
        
        # 3. Create obstacles for this robot's workspace
        workspace_name = ROBOT_WORKSPACES.get(robot_serial, 'office_floor_1')
        obstacle_templates = get_obstacles_for_workspace(workspace_name)
        
        print(f"Creating {len(obstacle_templates)} obstacles for workspace: {workspace_name}")
        for obs_template in obstacle_templates:
            obstacle = Obstacle(
                robot_id=robot.id,
                name=obs_template['name'],
                obstacle_type=obs_template['type'],
                x=obs_template['x'],
                y=obs_template['y'],
                width=obs_template.get('width'),
                height=obs_template.get('height'),
                radius=obs_template.get('radius'),
                color=obs_template.get('color', 'rgba(100,100,100,0.4)')
            )
            db.session.add(obstacle)
        
        db.session.commit()
        print(f"✓ Obstacles created for {robot_serial}")

        end_time = datetime.now(timezone.utc)
        start_time = end_time - timedelta(days=days_to_generate)
        
        telemetry_buffer = []
        path_buffer = []
        
        # Simulated values
        current_battery = 24.8
        cycle_count = 2700  # Starting cycle count (robot's lifetime power-on cycles)
        
        # Track last logged telemetry values for change detection
        last_logged_battery = current_battery
        last_logged_temp = 45
        last_logged_load = 30
        last_logged_status = "NOMINAL"
        last_telemetry_time = start_time
        
        # Track last position for smooth movement
        # Start at a valid position (avoid obstacles)
        last_pos_x = 30.0  # Start in open area (left side)
        last_pos_y = 90.0
        last_orientation = 0.0
        
        # Movement state
        movement_phase = 0  # Different patrol patterns
        idle_until = None   # Track when robot is idle/stationary
        
        # Power cycle tracking
        is_powered_on = True  # Robot starts powered on
        next_power_cycle_time = None  # When next power cycle should occur
        in_power_cycle = False  # Track if currently in a power cycle sequence
        power_cycle_boot_time = None  # When to complete boot after power-on
        
        # Schedule random power cycles (1-3 per day)
        power_cycle_schedule = []
        for day in range(days_to_generate):
            num_cycles = random.randint(1, 3)  # 1-3 power cycles per day
            for _ in range(num_cycles):
                # Random time during the day (not at night when robot should be charging)
                cycle_hour = random.randint(7, 21)  # Between 7 AM and 9 PM
                cycle_minute = random.randint(0, 59)
                cycle_time = start_time + timedelta(days=day, hours=cycle_hour, minutes=cycle_minute)
                power_cycle_schedule.append(cycle_time)
        
        power_cycle_schedule.sort()  # Ensure chronological order
        print(f"Scheduled {len(power_cycle_schedule)} power cycles over {days_to_generate} days")
        
        # Loop through time minute by minute
        total_minutes = days_to_generate * 24 * 60
        print(f"Generating {total_minutes} minutes of data...")
        
        for i in range(total_minutes):
            current_step_time = start_time + timedelta(minutes=i)
            
            # --- HANDLE POWER CYCLES ---
            # Check if it's time for a scheduled power cycle
            if power_cycle_schedule and not in_power_cycle:
                if current_step_time >= power_cycle_schedule[0]:
                    # Start power cycle: OFFLINE
                    in_power_cycle = True
                    is_powered_on = False
                    power_cycle_boot_time = current_step_time + timedelta(minutes=random.randint(2, 5))  # Boot after 2-5 minutes
                    power_cycle_schedule.pop(0)  # Remove this cycle from schedule
                    print(f"Power cycle {cycle_count + 1} started (OFFLINE) at {current_step_time.strftime('%Y-%m-%d %H:%M')}")
            
            # Check if it's time to boot after being offline
            if in_power_cycle and not is_powered_on and current_step_time >= power_cycle_boot_time:
                # Power back on: BOOTING
                is_powered_on = True
                cycle_count += 1  # INCREMENT CYCLE COUNT ON POWER-ON
                print(f"Power cycle {cycle_count} completed (BOOTING) at {current_step_time.strftime('%Y-%m-%d %H:%M')}")
                
                # Log BOOTING status immediately
                boot_log = TelemetryLog(
                    robot_id=robot.id,
                    timestamp=current_step_time,
                    battery_voltage=round(current_battery, 2),
                    cpu_temp=40,  # Cool after being off
                    motor_load=10,  # Low load during boot
                    cycle_counter=cycle_count,
                    status_code="BOOTING"
                )
                telemetry_buffer.append(boot_log)
                last_logged_status = "BOOTING"
                last_telemetry_time = current_step_time
                
                # Schedule return to normal operation (after 3 minutes)
                in_power_cycle = False
            
            # --- SIMULATE DAY/NIGHT CYCLES (Robot rests at night) ---
            hour_of_day = current_step_time.hour
            is_night = hour_of_day < 6 or hour_of_day >= 22  # 10 PM to 6 AM
            
            # Skip operations if powered off
            if not is_powered_on:
                # Log OFFLINE status once per 5 minutes
                if i % TELEMETRY_INTERVAL_MINS == 0:
                    if last_logged_status != "OFFLINE":
                        offline_log = TelemetryLog(
                            robot_id=robot.id,
                            timestamp=current_step_time,
                            battery_voltage=round(current_battery, 2),
                            cpu_temp=25,  # Ambient temp when off
                            motor_load=0,
                            cycle_counter=cycle_count,
                            status_code="OFFLINE"
                        )
                        telemetry_buffer.append(offline_log)
                        last_logged_status = "OFFLINE"
                        last_telemetry_time = current_step_time
                continue  # Skip movement and other operations
            
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
                    # Circular patrol (adjusted to avoid center obstacles)
                    target_x = 30 + (20 * math.cos(t))
                    target_y = 20 + (20 * math.sin(t))
                elif movement_phase == 2:
                    # Modified square patrol to avoid obstacles
                    phase = (t % (2 * math.pi)) / (2 * math.pi)
                    if phase < 0.25:
                        target_x = 10 + (phase * 4 * 50)
                        target_y = 15
                    elif phase < 0.5:
                        target_x = 60
                        target_y = 15 + ((phase - 0.25) * 4 * 20)
                    elif phase < 0.75:
                        target_x = 60 - ((phase - 0.5) * 4 * 50)
                        target_y = 35
                    else:
                        target_x = 10
                        target_y = 35 - ((phase - 0.75) * 4 * 20)
                else:
                    # Random walk in open spaces
                    target_x = 30 + (15 * math.sin(t)) + (10 * math.cos(t * 3))
                    target_y = 20 + (15 * math.cos(t)) + (10 * math.sin(t * 2.5))
                
                # Validate target position and find alternative if needed
                if not is_valid_position(target_x, target_y, obstacle_templates):
                    target_x, target_y = find_valid_position_near(target_x, target_y, obstacle_templates)
                
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
                
                # Validate final position before committing
                if not is_valid_position(pos_x, pos_y, obstacle_templates):
                    # If collision, stay at last position
                    pos_x = last_pos_x
                    pos_y = last_pos_y
                
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
            
            # Keep positions in bounds (0-100) - final safety check
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
                        cycle_counter=cycle_count,  # Use actual power-on cycle count, not time-based
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

def generate_synthetic_data():
    """Generate synthetic data for all configured robots"""
    print("=" * 80)
    print("SITARA DATA SEEDING - MULTIPLE ROBOTS")
    print("=" * 80)
    
    for robot_config in ROBOTS:
        generate_synthetic_data_for_robot(
            robot_serial=robot_config['serial'],
            operator_username=robot_config['operator'],
            days_to_generate=robot_config['days']
        )
        print()  # Blank line between robots
    
    print("=" * 80)
    print("ALL ROBOTS SEEDED SUCCESSFULLY")
    print("=" * 80)

if __name__ == "__main__":
    generate_synthetic_data()