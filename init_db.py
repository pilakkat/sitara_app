import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

from app import app, db, User

def init_users():
    with app.app_context():
        # Ensure database directory exists
        db_dir = os.path.join(os.path.dirname(__file__), 'database')
        if not os.path.exists(db_dir):
            os.makedirs(db_dir)
            print(f"Created directory: {db_dir}")
        
        db.create_all()
        
        # Get credentials from environment variables
        admin_username = os.getenv('ADMIN_USERNAME', 'admin')
        admin_password = os.getenv('ADMIN_PASSWORD')
        operator_username = os.getenv('OPERATOR_USERNAME', 'operator')
        operator_password = os.getenv('OPERATOR_PASSWORD')
        operator2_username = os.getenv('OPERATOR2_USERNAME', 'operator2')
        operator2_password = os.getenv('OPERATOR2_PASSWORD')
        operator3_username = os.getenv('OPERATOR3_USERNAME', 'operator3')
        operator3_password = os.getenv('OPERATOR3_PASSWORD')
        
        # Check if users exist
        if not User.query.filter_by(username=admin_username).first():
            if not admin_password:
                raise ValueError("ADMIN_PASSWORD environment variable is required")
            admin = User(username=admin_username, password=admin_password)
            db.session.add(admin)
            print(f"User '{admin_username}' created.")
            
        if not User.query.filter_by(username=operator_username).first():
            if not operator_password:
                raise ValueError("OPERATOR_PASSWORD environment variable is required")
            op = User(username=operator_username, password=operator_password)
            db.session.add(op)
            print(f"User '{operator_username}' created.")
        
        if not User.query.filter_by(username=operator2_username).first():
            if not operator2_password:
                raise ValueError("OPERATOR2_PASSWORD environment variable is required")
            op2 = User(username=operator2_username, password=operator2_password)
            db.session.add(op2)
            print(f"User '{operator2_username}' created.")
        
        if not User.query.filter_by(username=operator3_username).first():
            if not operator3_password:
                raise ValueError("OPERATOR3_PASSWORD environment variable is required")
            op3 = User(username=operator3_username, password=operator3_password)
            db.session.add(op3)
            print(f"User '{operator3_username}' created.")
            
        db.session.commit()
        print("Database initialized successfully.")

if __name__ == '__main__':
    init_users()