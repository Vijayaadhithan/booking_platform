from __future__ import absolute_import, unicode_literals
import os
from celery import Celery

# Set the default Django settings module for the 'celery' program.
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'booking_platform.settings')

app = Celery('booking_platform')

# Using a string here means the worker doesn't have to serialize
# the configuration object to child processes.
# Namespace 'CELERY' means all celery-related config keys
# should start with 'CELERY_'.
app.config_from_object('django.conf:settings', namespace='CELERY')

# Configure Redis broker URL with authentication
app.conf.broker_url = 'redis://:redis_password_123@redis:6379/0'
app.conf.result_backend = 'redis://:redis_password_123@redis:6379/0'

# Load task modules from all registered Django app configs.
app.autodiscover_tasks()

@app.task(bind=True)
def debug_task(self):
    print(f'Request: {self.request!r}')
