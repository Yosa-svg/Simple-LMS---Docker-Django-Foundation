# config/__init__.py
# Import celery app agar task auto-discovery berjalan saat Django startup.
# Ini memastikan shared_task menggunakan app ini.

from .celery import app as celery_app

__all__ = ('celery_app',)
