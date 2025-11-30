# Gunicorn configuration file for SITARA Robot Client
# Usage: gunicorn -c gunicorn.conf.py wsgi:app

import os
import multiprocessing

# Get configuration from environment
bind = f"0.0.0.0:{os.getenv('CLIENT_UI_PORT', '5001')}"

# Worker configuration
# Use only 1 worker to avoid multiple robot client instances
workers = 1
worker_class = "sync"
threads = 2

# Timeout settings
timeout = 120
graceful_timeout = 30
keepalive = 5

# Logging
loglevel = os.getenv('LOG_LEVEL', 'info')
accesslog = "-"  # Log to stdout
errorlog = "-"   # Log to stderr
access_log_format = '%(h)s %(l)s %(u)s %(t)s "%(r)s" %(s)s %(b)s "%(f)s" "%(a)s"'

# Process naming
proc_name = "sitara-robot-client"

# Server mechanics
daemon = False
pidfile = None
user = None
group = None
tmp_upload_dir = None

# Security
limit_request_line = 4094
limit_request_fields = 100
limit_request_field_size = 8190

# Worker lifecycle hooks
def on_starting(server):
    """Called just before the master process is initialized."""
    print(f"[GUNICORN] Starting SITARA Robot Client on {bind}")

def on_reload(server):
    """Called when worker processes are reloaded."""
    print("[GUNICORN] Reloading workers...")

def when_ready(server):
    """Called just after the server is started."""
    print(f"[GUNICORN] Server is ready. Accepting connections on {bind}")

def worker_int(worker):
    """Called when a worker receives the SIGINT or SIGQUIT signal."""
    print(f"[GUNICORN] Worker {worker.pid} received SIGINT/SIGQUIT")

def worker_abort(worker):
    """Called when a worker receives the SIGABRT signal."""
    print(f"[GUNICORN] Worker {worker.pid} received SIGABRT")
