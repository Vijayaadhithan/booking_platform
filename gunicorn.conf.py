# Gunicorn configuration file
import multiprocessing

# Worker settings
workers = multiprocessing.cpu_count() * 2 + 1
worker_class = 'sync'
worker_connections = 1000
timeout = 120  # Increase timeout to 120 seconds
keepalive = 2

# Server mechanics
max_requests = 1000
max_requests_jitter = 50
graceful_timeout = 30

# Logging
acceslog = '-'
errorlog = '-'
loglevel = 'info'

# Server socket
bind = '0.0.0.0:8000'
backlog = 2048

# Process naming
proc_name = 'booking_platform'

# SSL
# keyfile = '/path/to/keyfile'
# certfile = '/path/to/certfile'

# Security
limit_request_line = 4096
limit_request_fields = 100
limit_request_field_size = 8190