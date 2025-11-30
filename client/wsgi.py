"""
WSGI entry point for running the SITARA client Flask app with gunicorn.

Usage:
    gunicorn wsgi:app -b 0.0.0.0:5002 --workers 1

Note: The robot client background threads will need to be started separately.
For production use, consider running the robot client as a separate service.
"""

from client_app import control_app, initialize_robot_client
import sys

# Initialize the robot client when the module is loaded
# This ensures the client is ready when gunicorn imports this module
try:
    print("[WSGI] Initializing robot client...")
    initialize_robot_client()
    print("[WSGI] Robot client initialized successfully")
except ValueError as e:
    print(f"[WSGI] ERROR: Failed to initialize robot client: {e}")
    print("[WSGI] Flask app will start but robot control will not work")
    print("[WSGI] Please check your environment variables")
except Exception as e:
    print(f"[WSGI] ERROR: Unexpected error during initialization: {e}")
    sys.exit(1)

# Export the Flask app for gunicorn
app = control_app

if __name__ == "__main__":
    # If run directly, start the Flask development server
    print("[WSGI] Starting Flask development server...")
    app.run(host='0.0.0.0', port=5002, debug=False)
