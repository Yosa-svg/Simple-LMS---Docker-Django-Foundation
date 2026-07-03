"""
Seed script: Insert 500 dummy activity logs ke MongoDB.

Modul 11 — Digunakan untuk mengisi data testing agar endpoint analytics
            (popular-courses, daily-summary, enrollment-stats) mengembalikan
            data yang meaningful.

Cara menjalankan (dari dalam container app):
    docker-compose exec app python lms/seed_mongo.py

Cara menjalankan (dari host, jika Python tersedia di host):
    python lms/seed_mongo.py
"""

import os
import sys
import random
import django
from datetime import datetime, timedelta

# --- Setup Django environment ---
# Tambahkan project root ke sys.path agar bisa import settings
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from django.conf import settings
from pymongo import MongoClient


def seed_activity_logs():
    # Koneksi ke MongoDB
    client = MongoClient(
        settings.MONGO_URI,
        serverSelectionTimeoutMS=5000,
    )
    db = client[settings.MONGO_DB_NAME]
    collection = db['activity_logs']

    # Data dummy
    courses = [
        {'id': 1, 'name': 'Django Basics'},
        {'id': 2, 'name': 'Python Advanced'},
        {'id': 3, 'name': 'Docker Fundamentals'},
        {'id': 4, 'name': 'REST API Design'},
        {'id': 5, 'name': 'Database Optimization'},
        {'id': 6, 'name': 'Redis Caching'},
        {'id': 7, 'name': 'Authentication & Security'},
        {'id': 8, 'name': 'Automated Testing'},
    ]

    actions = ['view_course', 'enroll', 'post_comment', 'view_content',
               'submit_quiz', 'download_material', 'login']
    browsers = ['Chrome', 'Firefox', 'Safari', 'Edge']
    user_ids = list(range(1, 51))   # 50 simulated users

    print(f"Seeding MongoDB collection: {settings.MONGO_DB_NAME}.activity_logs ...")

    # Hapus data lama (opsional — komentari jika tidak ingin menghapus)
    deleted = collection.delete_many({})
    print(f"  Removed {deleted.deleted_count} existing documents.")

    logs = []
    for i in range(500):
        user_id  = random.choice(user_ids)
        action   = random.choice(actions)
        course   = random.choice(courses)
        days_ago = random.randint(0, 30)
        timestamp = datetime.utcnow() - timedelta(
            days=days_ago,
            hours=random.randint(0, 23),
            minutes=random.randint(0, 59),
        )

        log = {
            'user_id':   user_id,
            'username':  f'user{user_id}',
            'action':    action,
            'resource':  f"course:{course['id']}",
            'timestamp': timestamp,
            'ip_address': f'192.168.1.{random.randint(1, 254)}',
            'metadata': {
                'course_id':   course['id'],
                'course_name': course['name'],
                'browser':     random.choice(browsers),
            },
        }
        logs.append(log)

    result = collection.insert_many(logs)
    print(f"  Inserted {len(result.inserted_ids)} documents.")
    print(f"  Total documents now: {collection.count_documents({})}")

    # Buat recommended indexes
    print("\nCreating indexes ...")
    collection.create_index([('user_id', 1), ('timestamp', -1)],
                             name='user_id_timestamp')
    collection.create_index([('action', 1)],
                             name='action')
    collection.create_index([('metadata.course_id', 1), ('action', 1)],
                             name='course_action')
    print("  Indexes created: user_id_timestamp, action, course_action")
    print("\nDone! Run the following to verify:")
    print("  docker-compose exec mongodb mongosh -u admin -p password123 --eval")
    print("  'use simple_lms_logs; db.activity_logs.countDocuments()'")


if __name__ == '__main__':
    seed_activity_logs()
