"""
Celery application configuration untuk Simple LMS.

Modul 9 — Asynchronous Task Processing
Broker  : RabbitMQ (amqp://rabbitmq:5672)
Backend : Redis    (redis://redis:6379/1)

Tasks yang tersedia (lms/tasks.py):
    - send_enrollment_email      : Email konfirmasi saat student enroll
    - generate_certificate       : Generate sertifikat saat course selesai
    - update_course_statistics   : Update enrollment count (scheduled, setiap jam)
    - export_course_report       : Generate CSV report (async on-demand)

Monitoring:
    Flower dashboard : http://localhost:5555
    RabbitMQ UI      : http://localhost:15672
"""

import os
from celery import Celery

# Set default Django settings module untuk celery
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')

# Buat instance Celery dengan nama package 'config'
app = Celery('config')

# Load konfigurasi Celery dari Django settings (prefix CELERY_)
app.config_from_object('django.conf:settings', namespace='CELERY')

# Auto-discover tasks dari semua INSTALLED_APPS
# Celery akan mencari file tasks.py di setiap app
app.autodiscover_tasks()


@app.task(bind=True, ignore_result=True)
def debug_task(self):
    """Task debug untuk verifikasi Celery berjalan."""
    print(f'Request: {self.request!r}')
