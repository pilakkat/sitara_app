#!/usr/bin/env python3
"""Verify client database setup"""
import sqlite3
from datetime import datetime

DB_PATH = 'database/client.db'

def verify_database():
    """Verify database structure and content"""
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        print("=" * 60)
        print("CLIENT DATABASE VERIFICATION")
        print("=" * 60)
        
        # Check tables
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = [row[0] for row in cursor.fetchall()]
        print(f"\n✓ Tables ({len(tables)}): {', '.join(tables)}")
        
        # Check users
        cursor.execute("SELECT id, username, created_at FROM user")
        users = cursor.fetchall()
        print(f"\n✓ Users ({len(users)}):")
        for user in users:
            print(f"  - ID {user[0]}: {user[1]} (created: {user[2]})")
        
        # Check robots
        cursor.execute("""
            SELECT id, serial_number, model_type, assigned_user_id,
                   version_rcpcu, version_rcspm, version_rcmmc, version_rcpmu
            FROM robot
        """)
        robots = cursor.fetchall()
        print(f"\n✓ Robots ({len(robots)}):")
        for robot in robots:
            print(f"  - ID {robot[0]}: {robot[1]} ({robot[2]})")
            print(f"    Assigned to User ID: {robot[3]}")
            print(f"    Versions: RCPCU={robot[4]}, RCSPM={robot[5]}, RCMMC={robot[6]}, RCPMU={robot[7]}")
        
        # Check software versions
        cursor.execute("""
            SELECT component, current_version, available_version, 
                   update_pending, release_date, last_checked
            FROM software_versions
            ORDER BY component
        """)
        versions = cursor.fetchall()
        print(f"\n✓ Software Version Tracking ({len(versions)} components):")
        for version in versions:
            pending = "YES" if version[3] else "NO"
            print(f"  - {version[0]}: v{version[1]} (available: v{version[2]}, pending: {pending})")
            if version[4]:
                print(f"    Release Date: {version[4]}")
            if version[5]:
                print(f"    Last Checked: {version[5]}")
        
        # Check version history
        cursor.execute("SELECT COUNT(*) FROM version_history")
        history_count = cursor.fetchone()[0]
        print(f"\n✓ Version History: {history_count} records")
        
        if history_count > 0:
            cursor.execute("""
                SELECT component, old_version, new_version, updated_at
                FROM version_history
                ORDER BY updated_at DESC
                LIMIT 5
            """)
            history = cursor.fetchall()
            print("  Recent updates:")
            for record in history:
                print(f"    - {record[0]}: {record[1]} → {record[2]} ({record[3]})")
        
        # Database info
        cursor.execute("SELECT page_count * page_size as size FROM pragma_page_count(), pragma_page_size()")
        db_size = cursor.fetchone()[0]
        print(f"\n✓ Database Size: {db_size:,} bytes ({db_size/1024:.1f} KB)")
        
        print("\n" + "=" * 60)
        print("DATABASE VERIFICATION COMPLETE")
        print("=" * 60)
        
        conn.close()
        return True
        
    except Exception as e:
        print(f"❌ Error: {e}")
        return False

if __name__ == '__main__':
    verify_database()
