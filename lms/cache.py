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
