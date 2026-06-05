# lms/mongo_logger.py
"""
MongoDB Activity Logger untuk Simple LMS.

Modul 9 — Document Storage:
    MongoDB dipilih untuk activity logs karena:
    1. Schema-less: setiap event bisa memiliki metadata berbeda
    2. Write-optimized: log ditulis lebih sering dari dibaca
    3. Tidak perlu join: setiap log document self-contained
    4. Time-series friendly: mudah query per rentang waktu

Collections:
    - activity_logs   : General activity log (login, view course, dll)
    - learning_analytics: Data analytics per user per course

Cara akses:
    python manage.py shell
    >>> from lms.mongo_logger import get_user_activity
    >>> get_user_activity(1)
"""

import logging
from datetime import datetime
from django.conf import settings

logger = logging.getLogger(__name__)


def _get_mongo_db():
    """
    Mendapatkan koneksi ke MongoDB database.

    Returns:
        pymongo.database.Database | None: MongoDB database instance,
        atau None jika koneksi gagal (fail gracefully).
    """
    try:
        from pymongo import MongoClient
        client = MongoClient(
            settings.MONGO_URI,
            serverSelectionTimeoutMS=3000,  # 3 detik timeout
            connectTimeoutMS=3000,
        )
        return client[settings.MONGO_DB_NAME]
    except Exception as e:
        logger.error(f"[MongoDB] Connection failed: {e}")
        return None


def log_activity(
    action: str,
    resource: str,
    user_id: int = None,
    username: str = None,
    metadata: dict = None,
    ip_address: str = None,
):
    """
    Mencatat aktivitas user ke MongoDB activity_logs collection.

    Args:
        action    : Nama aksi (contoh: 'login', 'view_course', 'enroll', 'comment')
        resource  : Resource yang diakses (contoh: 'course:1', 'comment:42')
        user_id   : ID user (opsional, None untuk anonymous)
        username  : Username (opsional, untuk kemudahan query)
        metadata  : Data tambahan dalam bentuk dict (opsional)
        ip_address: IP address client (opsional)

    Example:
        log_activity('enroll', 'course:5', user_id=3, username='budi',
                     metadata={'course_name': 'Django 101'})
    """
    db = _get_mongo_db()
    if db is None:
        return  # Fail gracefully

    try:
        document = {
            'action': action,
            'resource': resource,
            'user_id': user_id,
            'username': username,
            'timestamp': datetime.utcnow(),
            'ip_address': ip_address,
            'metadata': metadata or {},
        }
        db['activity_logs'].insert_one(document)
        logger.debug(f"[MongoDB] Logged: {action} on {resource} by user:{user_id}")
    except Exception as e:
        logger.error(f"[MongoDB] log_activity failed: {e}")


def log_enrollment(user_id: int, username: str, course_id: int, course_name: str):
    """
    Mencatat event enrollment ke MongoDB.
    Shortcut untuk log_activity dengan action='enroll'.

    Args:
        user_id    : ID student
        username   : Username student
        course_id  : ID course
        course_name: Nama course
    """
    log_activity(
        action='enroll',
        resource=f'course:{course_id}',
        user_id=user_id,
        username=username,
        metadata={
            'course_id': course_id,
            'course_name': course_name,
        }
    )


def log_course_view(user_id: int, username: str, course_id: int):
    """
    Mencatat event view course ke MongoDB.

    Args:
        user_id  : ID user
        username : Username
        course_id: ID course yang dilihat
    """
    log_activity(
        action='view_course',
        resource=f'course:{course_id}',
        user_id=user_id,
        username=username,
        metadata={'course_id': course_id}
    )


def get_user_activity(user_id: int, limit: int = 20) -> list:
    """
    Mengambil history aktivitas user dari MongoDB.

    Args:
        user_id: ID user
        limit  : Jumlah maksimum dokumen yang diambil (default: 20)

    Returns:
        list: Daftar dokumen aktivitas (tanpa _id MongoDB)
    """
    db = _get_mongo_db()
    if db is None:
        return []

    try:
        cursor = (
            db['activity_logs']
            .find({'user_id': user_id}, {'_id': 0})  # Exclude _id MongoDB
            .sort('timestamp', -1)                   # Terbaru dulu
            .limit(limit)
        )
        return list(cursor)
    except Exception as e:
        logger.error(f"[MongoDB] get_user_activity failed: {e}")
        return []


def get_enrollment_stats() -> dict:
    """
    Aggregation query untuk statistik enrollment.

    Menggunakan MongoDB aggregation pipeline untuk menghitung
    jumlah enrollment per course.

    Returns:
        dict: {'total_enrollments': int, 'by_course': list}
    """
    db = _get_mongo_db()
    if db is None:
        return {'total_enrollments': 0, 'by_course': []}

    try:
        pipeline = [
            {'$match': {'action': 'enroll'}},
            {'$group': {
                '_id': '$metadata.course_id',
                'course_name': {'$first': '$metadata.course_name'},
                'count': {'$sum': 1},
            }},
            {'$sort': {'count': -1}},
            {'$limit': 10},
        ]
        by_course = list(db['activity_logs'].aggregate(pipeline))

        total = db['activity_logs'].count_documents({'action': 'enroll'})
        return {
            'total_enrollments': total,
            'by_course': by_course,
        }
    except Exception as e:
        logger.error(f"[MongoDB] get_enrollment_stats failed: {e}")
        return {'total_enrollments': 0, 'by_course': []}
