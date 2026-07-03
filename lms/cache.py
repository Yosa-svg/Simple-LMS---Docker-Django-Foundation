# lms/cache.py
"""
Redis Caching Utilities untuk Simple LMS.

Modul 9 — Caching Strategy:
    - Course list  : TTL 5 menit  (data relatif statis, sering dibaca)
    - Course detail: TTL 10 menit (data lebih spesifik)
    - Cache invalidation: Dipanggil saat course diubah/dihapus

Menggunakan django-redis sebagai cache backend.
Konfigurasi di settings.py → CACHES.

Pola cache yang digunakan: Cache-Aside (Lazy Loading)
    1. Cek cache terlebih dahulu
    2. Jika cache miss → ambil dari DB → simpan ke cache
    3. Jika cache hit → langsung return data

Keuntungan:
    - Mengurangi query ke database PostgreSQL
    - Response time lebih cepat untuk data populer
    - Auto-expire jika TTL habis (eventual consistency)
"""

import json
import logging
from django.core.cache import cache
from django_redis import get_redis_connection

logger = logging.getLogger(__name__)

# ==============================================================================
# CACHE KEY CONSTANTS
# ==============================================================================

CACHE_KEY_COURSE_LIST = 'course_list'
CACHE_KEY_COURSE_DETAIL = 'course_detail_{id}'
CACHE_KEY_RATE_LIMIT = 'rate_limit_{ip}_{endpoint}'

# TTL dalam detik
TTL_COURSE_LIST = 60 * 5      # 5 menit
TTL_COURSE_DETAIL = 60 * 10   # 10 menit
TTL_RATE_LIMIT = 60           # 1 menit (window rate limiting)


# ==============================================================================
# COURSE CACHING
# ==============================================================================

def get_cached_course_list():
    """
    Mengambil daftar course dari cache.

    Returns:
        list | None: Data course dari cache, atau None jika cache miss
    """
    return cache.get(CACHE_KEY_COURSE_LIST)


def set_course_list_cache(data):
    """
    Menyimpan daftar course ke cache.

    Args:
        data: Data courses (list of dict yang sudah di-serialize)
    """
    cache.set(CACHE_KEY_COURSE_LIST, data, TTL_COURSE_LIST)
    logger.debug(f"[Cache] SET course_list (TTL: {TTL_COURSE_LIST}s)")


def get_cached_course_detail(course_id: int):
    """
    Mengambil detail course dari cache.

    Args:
        course_id: ID course yang dicari

    Returns:
        dict | None: Data course dari cache, atau None jika cache miss
    """
    key = CACHE_KEY_COURSE_DETAIL.format(id=course_id)
    return cache.get(key)


def set_course_detail_cache(course_id: int, data):
    """
    Menyimpan detail course ke cache.

    Args:
        course_id: ID course
        data     : Data course (dict yang sudah di-serialize)
    """
    key = CACHE_KEY_COURSE_DETAIL.format(id=course_id)
    cache.set(key, data, TTL_COURSE_DETAIL)
    logger.debug(f"[Cache] SET course_detail:{course_id} (TTL: {TTL_COURSE_DETAIL}s)")


def invalidate_course_cache(course_id: int = None):
    """
    Menghapus cache course.

    Cache invalidation dipanggil saat:
    - Course dibuat baru (invalidate list)
    - Course diupdate (invalidate list + detail course tersebut)
    - Course dihapus  (invalidate list + detail course tersebut)

    Args:
        course_id: ID course yang diinvalidate. Jika None, hanya invalidate list.
    """
    # Selalu invalidate list karena ada perubahan
    cache.delete(CACHE_KEY_COURSE_LIST)
    logger.debug("[Cache] DELETE course_list")

    if course_id is not None:
        key = CACHE_KEY_COURSE_DETAIL.format(id=course_id)
        cache.delete(key)
        logger.debug(f"[Cache] DELETE course_detail:{course_id}")


# ==============================================================================
# RATE LIMITING
# ==============================================================================

def check_rate_limit(ip: str, endpoint: str, max_requests: int = 60) -> bool:
    """
    Memeriksa dan mengupdate rate limit untuk IP + endpoint tertentu.

    Menggunakan sliding window counter dengan Redis.
    Window: 1 menit (60 detik).

    Args:
        ip          : IP address client
        endpoint    : Nama endpoint (contoh: 'sign-in')
        max_requests: Maksimum request per menit (default: 60)

    Returns:
        bool: True jika masih dalam batas, False jika sudah melebihi limit
    """
    key = CACHE_KEY_RATE_LIMIT.format(ip=ip, endpoint=endpoint)

    try:
        current = cache.get(key, 0)
        if current >= max_requests:
            logger.warning(f"[RateLimit] EXCEEDED: {ip} → {endpoint} ({current}/{max_requests})")
            return False  # Melebihi batas

        # Increment counter
        cache.set(key, current + 1, TTL_RATE_LIMIT)
        return True  # Masih dalam batas
    except Exception as e:
        # Jika Redis down, jangan block request (fail open)
        logger.error(f"[RateLimit] Redis error: {e}. Allowing request.")
        return True


def get_rate_limit_info(ip: str, endpoint: str) -> dict:
    """
    Mengambil informasi rate limit saat ini untuk debugging.

    Args:
        ip      : IP address client
        endpoint: Nama endpoint

    Returns:
        dict: {'current': int, 'limit': int, 'remaining': int}
    """
    key = CACHE_KEY_RATE_LIMIT.format(ip=ip, endpoint=endpoint)
    current = cache.get(key, 0)
    limit = 60
    return {
        'current': current,
        'limit': limit,
        'remaining': max(0, limit - current),
    }


# ==============================================================================
# LEADERBOARD (SORTED SETS)
# ==============================================================================

def get_redis_client():
    """Mengembalikan koneksi Redis raw dari django-redis."""
    return get_redis_connection("default")


def increment_course_popularity(course_id: int, amount: int = 1):
    """
    Menambahkan score popularitas (enrollment) ke sorted set 'popular_courses'.
    """
    client = get_redis_client()
    # ZINCRBY popular_courses <amount> course:<id>
    client.zincrby('popular_courses', amount, f'course:{course_id}')
    logger.debug(f"[Redis] Incremented popularity for course:{course_id} by {amount}")


def get_popular_courses(limit: int = 10):
    """
    Mengambil top N courses terpopuler.
    Returns list of tuples: [(course_id, score), ...]
    """
    client = get_redis_client()
    # ZREVRANGE popular_courses 0 <limit-1> WITHSCORES
    # Result format from redis-py: [(b'course:1', 150.0), ...]
    results = client.zrevrange('popular_courses', 0, limit - 1, withscores=True)
    
    parsed_results = []
    for item, score in results:
        # Decode bytes if needed (depends on redis-py version and decode_responses flag)
        item_str = item.decode('utf-8') if isinstance(item, bytes) else item
        # item_str format is "course:123"
        course_id = int(item_str.split(':')[1])
        parsed_results.append((course_id, int(score)))
        
    return parsed_results


def sync_popularity_from_db():
    """
    Sinkronisasi awal dari DB ke Redis Sorted Set jika Redis kosong/terhapus.
    Menghitung jumlah enrollment dari tabel CourseMember untuk masing-masing course.
    """
    from lms.models import Course, CourseMember
    from django.db.models import Count
    
    client = get_redis_client()
    
    # Ambil jumlah student (role='std') per course
    stats = CourseMember.objects.filter(roles='std').values('course_id').annotate(count=Count('id'))
    
    for stat in stats:
        course_id = stat['course_id']
        count = stat['count']
        client.zadd('popular_courses', {f'course:{course_id}': count})
        
    logger.info("[Redis] Synchronized popular_courses from database")
