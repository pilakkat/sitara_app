"""
Client Database Manager
Handles all database operations for the robot client
"""
import sqlite3
import os
from datetime import datetime, timezone
from contextlib import contextmanager

DB_DIR = os.path.join(os.path.dirname(__file__), 'database')
DB_PATH = os.path.join(DB_DIR, 'client.db')

class ClientDatabase:
    """Database manager for client-side operations"""
    
    def __init__(self, db_path=None):
        self.db_path = db_path or DB_PATH
        self._ensure_db_exists()
    
    def _ensure_db_exists(self):
        """Ensure database file exists"""
        if not os.path.exists(self.db_path):
            print(f"[DB] Database not found. Please run init_client_db.py first")
    
    @contextmanager
    def get_connection(self):
        """Context manager for database connections"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row  # Return rows as dictionaries
        try:
            yield conn
            conn.commit()
        except Exception as e:
            conn.rollback()
            raise e
        finally:
            conn.close()
    
    # ===== USER OPERATIONS =====
    
    def get_user(self, username):
        """Get user by username"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT * FROM user WHERE username = ?', (username,))
            return cursor.fetchone()
    
    def verify_credentials(self, username, password):
        """Verify user credentials"""
        user = self.get_user(username)
        if user and user['password'] == password:
            return True
        return False
    
    def update_user_password(self, username, new_password):
        """Update user password"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('UPDATE user SET password = ? WHERE username = ?',
                         (new_password, username))
            return cursor.rowcount > 0
    
    # ===== ROBOT OPERATIONS =====
    
    def get_robot(self, robot_id):
        """Get robot by ID"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT * FROM robot WHERE id = ?', (robot_id,))
            return cursor.fetchone()
    
    def get_robot_versions(self, robot_id):
        """Get current software versions for robot"""
        robot = self.get_robot(robot_id)
        if robot:
            return {
                'RCPCU': robot['version_rcpcu'],
                'RCSPM': robot['version_rcspm'],
                'RCMMC': robot['version_rcmmc'],
                'RCPMU': robot['version_rcpmu']
            }
        return None
    
    def update_robot_versions(self, robot_id, versions):
        """Update robot software versions"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                UPDATE robot 
                SET version_rcpcu = ?, version_rcspm = ?, version_rcmmc = ?, version_rcpmu = ?,
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
            ''', (versions.get('RCPCU'), versions.get('RCSPM'), 
                  versions.get('RCMMC'), versions.get('RCPMU'), robot_id))
            return cursor.rowcount > 0
    
    def update_last_version_check(self, robot_id):
        """Update last version check timestamp"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                UPDATE robot 
                SET last_version_check = CURRENT_TIMESTAMP,
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
            ''', (robot_id,))
            return cursor.rowcount > 0
    
    # ===== SOFTWARE VERSION OPERATIONS =====
    
    def get_software_version(self, component):
        """Get software version info for a component"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT * FROM software_versions WHERE component = ?', 
                         (component,))
            return cursor.fetchone()
    
    def get_all_software_versions(self):
        """Get all software versions"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT * FROM software_versions ORDER BY component')
            return cursor.fetchall()
    
    def update_available_version(self, robot_id, component, available_version, release_date=None, release_notes=None):
        """Update available version from server and check against robot's current version"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            
            # Get robot's current version from robot table
            column_map = {
                'RCPCU': 'version_rcpcu',
                'RCSPM': 'version_rcspm',
                'RCMMC': 'version_rcmmc',
                'RCPMU': 'version_rcpmu'
            }
            
            if component not in column_map:
                return False
            
            cursor.execute(f'SELECT {column_map[component]} FROM robot WHERE id = ?', (robot_id,))
            result = cursor.fetchone()
            
            if not result:
                return False
            
            current_version = result[0]
            
            # Don't flag update as pending if available version is 'unknown'
            update_pending = 1 if (available_version != current_version and available_version != 'unknown') else 0
            
            # Check if entry exists in software_versions
            cursor.execute('SELECT id FROM software_versions WHERE component = ?', (component,))
            exists = cursor.fetchone()
            
            if exists:
                cursor.execute('''
                    UPDATE software_versions 
                    SET available_version = ?, release_date = ?, release_notes = ?,
                        update_pending = ?, last_checked = CURRENT_TIMESTAMP,
                        updated_at = CURRENT_TIMESTAMP
                    WHERE component = ?
                ''', (available_version, release_date, release_notes, update_pending, component))
            else:
                # Insert if doesn't exist
                cursor.execute('''
                    INSERT INTO software_versions 
                    (component, current_version, available_version, release_date, release_notes, update_pending)
                    VALUES (?, ?, ?, ?, ?, ?)
                ''', (component, current_version, available_version, release_date, release_notes, update_pending))
            
            return cursor.rowcount > 0
    
    def apply_software_update(self, robot_id, component, new_version):
        """Apply software update for a component"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            
            # Get current version
            version_info = self.get_software_version(component)
            if not version_info:
                return False
            
            old_version = version_info['current_version']
            
            # Update software_versions table
            cursor.execute('''
                UPDATE software_versions 
                SET current_version = ?, update_pending = 0,
                    updated_at = CURRENT_TIMESTAMP
                WHERE component = ?
            ''', (new_version, component))
            
            # Update robot table
            column_map = {
                'RCPCU': 'version_rcpcu',
                'RCSPM': 'version_rcspm',
                'RCMMC': 'version_rcmmc',
                'RCPMU': 'version_rcpmu'
            }
            
            if component in column_map:
                cursor.execute(f'''
                    UPDATE robot 
                    SET {column_map[component]} = ?, updated_at = CURRENT_TIMESTAMP
                    WHERE id = ?
                ''', (new_version, robot_id))
            
            # Record in version history
            cursor.execute('''
                INSERT INTO version_history (robot_id, component, old_version, new_version)
                VALUES (?, ?, ?, ?)
            ''', (robot_id, component, old_version, new_version))
            
            return True
    
    def get_pending_updates(self, robot_id):
        """Get list of components with pending updates for a specific robot"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            
            # Get robot's current versions
            cursor.execute('''
                SELECT version_rcpcu, version_rcspm, version_rcmmc, version_rcpmu 
                FROM robot WHERE id = ?
            ''', (robot_id,))
            robot = cursor.fetchone()
            
            if not robot:
                return []
            
            current_versions = {
                'RCPCU': robot['version_rcpcu'],
                'RCSPM': robot['version_rcspm'],
                'RCMMC': robot['version_rcmmc'],
                'RCPMU': robot['version_rcpmu']
            }
            
            # Get available versions
            cursor.execute('''
                SELECT component, available_version, release_notes
                FROM software_versions 
                WHERE update_pending = 1
                ORDER BY component
            ''')
            
            updates = []
            for row in cursor.fetchall():
                component = row['component']
                updates.append({
                    'component': component,
                    'current_version': current_versions.get(component, '0.0.0'),
                    'available_version': row['available_version'],
                    'release_notes': row['release_notes']
                })
            
            return updates
    
    def get_version_history(self, robot_id, limit=10):
        """Get version update history for robot"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT * FROM version_history 
                WHERE robot_id = ?
                ORDER BY updated_at DESC
                LIMIT ?
            ''', (robot_id, limit))
            return cursor.fetchall()
    
    # ===== UTILITY METHODS =====
    
    def get_database_info(self):
        """Get database information"""
        info = {
            'path': self.db_path,
            'exists': os.path.exists(self.db_path),
            'size_bytes': os.path.getsize(self.db_path) if os.path.exists(self.db_path) else 0
        }
        
        if info['exists']:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT COUNT(*) as count FROM user")
                info['user_count'] = cursor.fetchone()['count']
                
                cursor.execute("SELECT COUNT(*) as count FROM robot")
                info['robot_count'] = cursor.fetchone()['count']
                
                cursor.execute("SELECT COUNT(*) as count FROM software_versions")
                info['version_count'] = cursor.fetchone()['count']
        
        return info
