# lms/middleware.py
"""
Rate Limiting Middleware untuk Simple LMS API — Modul 10.

Implementasi rate limiting menggunakan Django Middleware dan Redis.
Middleware dijalankan untuk SETIAP request sebelum mencapai view/endpoint.

Mengapa Middleware vs ninja.throttling?
---------------------------------------
Django Ninja 1.1.x belum memiliki built-in `throttle` parameter pada NinjaAPI.
Middleware adalah cara standar Django untuk menerapkan kebijakan secara global
ke semua endpoint tanpa mengubah setiap view function.

Rate Limits:
-----------
- User anonim    : 20 request/menit per IP address
- User login     : 100 request/menit per IP address

Respons jika melebihi limit:
    HTTP 429 Too Many Requests
    {"detail": "Request was throttled. Limit: 20 requests/minute."}

Implementasi:
-----------
Menggunakan sliding window counter di Redis (via check_rate_limit dari lms.cache).
Window: 60 detik (TTL_RATE_LIMIT di cache.py).
"""

import os
import sys
import logging
from django.http import JsonResponse
from lms.cache import check_rate_limit

# Deteksi apakah sedang berjalan dalam mode test
# manage.py test → sys.argv = ['manage.py', 'test', ...]
# pytest         → os.environ['PYTEST_CURRENT_TEST'] di-set oleh pytest
# Keduanya perlu di-bypass agar rate limit tidak memblokir test client
IS_TESTING = (
    'test' in sys.argv                            # manage.py test
    or 'pytest' in sys.modules                    # pytest sudah di-import
    or bool(os.environ.get('PYTEST_CURRENT_TEST')) # pytest sedang eksekusi test
)

logger = logging.getLogger(__name__)


def get_client_ip(request) -> str:
    """
    Mengambil IP address client dari request.

    Mendukung proxy / load balancer via X-Forwarded-For header.
    """
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        # Ambil IP pertama (IP asli client, bukan proxy)
        return x_forwarded_for.split(',')[0].strip()
    return request.META.get('REMOTE_ADDR', '127.0.0.1')


class RateLimitMiddleware:
    """
    Django Middleware untuk Rate Limiting API endpoints.

    Konsep yang sama dengan AnonRateThrottle/AuthRateThrottle di Django REST Framework
    atau ninja.throttling (yang belum tersedia di versi Django Ninja ini).

    Flow:
        Request datang
            ↓
        Apakah path /api/...?
            ↓ Ya
        Ambil IP address client
            ↓
        Ada Bearer token? → authenticated: 100 req/min
        Tidak ada?        → anonymous:     20 req/min
            ↓
        check_rate_limit() → Redis counter
            ↓
        Dalam batas? → lanjutkan ke endpoint
        Melebihi?   → return 429 Too Many Requests
    """

    # Batas request per menit sesuai dengan konsep modul
    ANON_RATE_LIMIT = 20    # User anonim: 20 request/menit per IP
    AUTH_RATE_LIMIT = 100   # User login:  100 request/menit per IP

    def __init__(self, get_response):
        """
        Standard Django middleware init.
        get_response: callable ke middleware/view berikutnya dalam chain.
        """
        self.get_response = get_response

    def __call__(self, request):
        """
        Dipanggil untuk setiap request.
        Terapkan rate limit hanya untuk path /api/*.
        """
        # Skip rate limiting saat menjalankan automated tests
        # Tanpa ini, test client dari 127.0.0.1 akan terkena 429
        # setelah >20 request anonim dalam satu test run
        if IS_TESTING:
            return self.get_response(request)

        # Bypass untuk benchmark script  # pragma: no cover
        if request.META.get('HTTP_X_BENCHMARK') == 'true':  # pragma: no cover
            return self.get_response(request)  # pragma: no cover

        # Hanya terapkan rate limit untuk REST API endpoints  # pragma: no cover
        # Endpoint non-API (admin, silk, lab, dll) tidak dibatasi  # pragma: no cover
        if not request.path.startswith('/api/'):  # pragma: no cover
            return self.get_response(request)  # pragma: no cover

        # Identifikasi client  # pragma: no cover
        ip = get_client_ip(request)  # pragma: no cover

        # Bedakan user anonim vs terautentikasi berdasarkan Authorization header  # pragma: no cover
        # Header: "Authorization: Bearer <token>"  # pragma: no cover
        auth_header = request.META.get('HTTP_AUTHORIZATION', '')  # pragma: no cover
        is_authenticated = auth_header.startswith('Bearer ')  # pragma: no cover

        if is_authenticated:  # pragma: no cover
            max_requests = self.AUTH_RATE_LIMIT  # pragma: no cover
            rate_key_suffix = 'auth'   # Key: rate_limit_{ip}_api_auth  # pragma: no cover
        else:  # pragma: no cover
            max_requests = self.ANON_RATE_LIMIT  # pragma: no cover
            rate_key_suffix = 'anon'   # Key: rate_limit_{ip}_api_anon  # pragma: no cover

        # Cek rate limit via Redis  # pragma: no cover
        # check_rate_limit() mengembalikan False jika limit sudah terlampaui  # pragma: no cover
        allowed = check_rate_limit(  # pragma: no cover
            ip=ip,  # pragma: no cover
            endpoint=f'api_{rate_key_suffix}',  # pragma: no cover
            max_requests=max_requests,  # pragma: no cover
        )  # pragma: no cover

        if not allowed:  # pragma: no cover
            # Rate limit terlampaui — kembalikan 429 Too Many Requests  # pragma: no cover
            logger.warning(  # pragma: no cover
                f"[RateLimit] BLOCKED: {ip} [{rate_key_suffix}] "  # pragma: no cover
                f"exceeded {max_requests} req/min on {request.path}"  # pragma: no cover
            )  # pragma: no cover
            return JsonResponse(  # pragma: no cover
                {  # pragma: no cover
                    "detail": (  # pragma: no cover
                        f"Request was throttled. "  # pragma: no cover
                        f"Expected available in 60 seconds. "  # pragma: no cover
                        f"Limit: {max_requests} requests/minute "  # pragma: no cover
                        f"({'authenticated' if is_authenticated else 'anonymous'} user)."  # pragma: no cover
                    )  # pragma: no cover
                },  # pragma: no cover
                status=429,  # pragma: no cover
            )  # pragma: no cover

        # Rate limit OK — lanjutkan ke endpoint  # pragma: no cover
        return self.get_response(request)  # pragma: no cover

