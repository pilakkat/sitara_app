"""
Initialize client-side database
Creates tables for robot info, user credentials, and software versions
"""
import sqlite3
import os
from datetime import datetime, timezone

# Database path
DB_DIR = os.path.join(os.path.dirname(__file__), 'database')
DB_PATH = os.path.join(DB_DIR, 'client.db')

def init_database():
    """Initialize the client database with required tables"""
    
    # Create database directory if it doesn't exist
    if not os.path.exists(DB_DIR):
        os.makedirs(DB_DIR)
        print(f"Created database directory: {DB_DIR}")
    
    # Connect to database
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # Create User table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS user (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # Create Robot table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS robot (
            id INTEGER PRIMARY KEY,
            serial_number TEXT UNIQUE NOT NULL,
            model_type TEXT DEFAULT "32DOF-HUMANOID",
            assigned_user_id INTEGER,
            version_rcpcu TEXT DEFAULT "0.0.0",
            version_rcspm TEXT DEFAULT "0.0.0",
            version_rcmmc TEXT DEFAULT "0.0.0",
            version_rcpmu TEXT DEFAULT "0.0.0",
            last_version_check TIMESTAMP,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (assigned_user_id) REFERENCES user(id)
        )
    ''')
    
    # Create SoftwareVersions table to track available updates
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS software_versions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            component TEXT NOT NULL,
            current_version TEXT NOT NULL,
            available_version TEXT,
            release_date TEXT,
            release_notes TEXT,
            update_pending INTEGER DEFAULT 0,
            last_checked TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # Create VersionHistory table to track version changes
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS version_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            robot_id INTEGER NOT NULL,
            component TEXT NOT NULL,
            old_version TEXT NOT NULL,
            new_version TEXT NOT NULL,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (robot_id) REFERENCES robot(id)
        )
    ''')
    
    conn.commit()
    conn.close()
    
    print(f"✓ Database initialized: {DB_PATH}")
    print("✓ Tables created: user, robot, software_versions, version_history")

def seed_initial_data(robot_id, username, password, serial_number=None):
    """Seed initial data for the client"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # Check if user exists
    cursor.execute('SELECT id FROM user WHERE username = ?', (username,))
    user = cursor.fetchone()
    
    if not user:
        # Create user
        cursor.execute('INSERT INTO user (username, password) VALUES (?, ?)', 
                      (username, password))
        user_id = cursor.lastrowid
        print(f"✓ Created user: {username}")
    else:
        user_id = user[0]
        print(f"✓ User already exists: {username}")
    
    # Check if robot exists
    cursor.execute('SELECT id FROM robot WHERE id = ?', (robot_id,))
    robot = cursor.fetchone()
    
    if not robot:
        # Generate serial number if not provided
        if not serial_number:
            serial_number = f"STR-{robot_id:04d}"
        
        # Create robot with default versions
        cursor.execute('''
            INSERT INTO robot (id, serial_number, assigned_user_id, 
                             version_rcpcu, version_rcspm, version_rcmmc, version_rcpmu)
            VALUES (?, ?, ?, '2.3.1', '1.8.5', '3.1.2', '1.5.9')
        ''', (robot_id, serial_number, user_id))
        print(f"✓ Created robot: ID={robot_id}, Serial={serial_number}")
    else:
        print(f"✓ Robot already exists: ID={robot_id}")
    
    # Initialize software versions tracking
    components = ['RCPCU', 'RCSPM', 'RCMMC', 'RCPMU']
    current_versions = ['2.3.1', '1.8.5', '3.1.2', '1.5.9']
    
    for component, version in zip(components, current_versions):
        cursor.execute('SELECT id FROM software_versions WHERE component = ?', (component,))
        if not cursor.fetchone():
            cursor.execute('''
                INSERT INTO software_versions (component, current_version)
                VALUES (?, ?)
            ''', (component, version))
    
    print(f"✓ Initialized software version tracking")
    
    conn.commit()
    conn.close()

if __name__ == '__main__':
    print("=" * 60)
    print("SITARA CLIENT DATABASE INITIALIZATION")
    print("=" * 60)
    
    init_database()
    
    # Example: Seed data for robot 1
    # You can customize this or run it separately
    import sys
    if len(sys.argv) > 1:
        robot_id = int(sys.argv[1])
        username = sys.argv[2] if len(sys.argv) > 2 else 'deepak'
        password = sys.argv[3] if len(sys.argv) > 3 else 'password'
        seed_initial_data(robot_id, username, password)
    
    print("=" * 60)
    print("Database ready!")
    print("=" * 60)
