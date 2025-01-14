from __future__ import absolute_import, unicode_literals

# This will make sure the app is always imported when
# Django starts, allowing Celery tasks to be recognized.
from .celery import app as celery_app

__all__ = ('celery_app',)
