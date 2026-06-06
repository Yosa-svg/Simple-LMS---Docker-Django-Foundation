"""
URL configuration for Simple LMS project.
"""
from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from lms.apiv1 import apiv1
from lms.apiv2 import apiv2

urlpatterns = [
    path('admin/', admin.site.urls),

    # Django Silk - Query Profiling Dashboard
    # Akses di: http://localhost:8000/silk/
    path('silk/', include('silk.urls', namespace='silk')),

    # Endpoint Lab - Optimasi Query (baseline vs optimized)
    path('lab/', include('lms.urls')),

    # REST API v1 — Django Ninja (Modul 6 - Modul 9)
    # Swagger UI : http://localhost:8000/api/v1/docs
    # OpenAPI    : http://localhost:8000/api/v1/openapi.json
    path('api/v1/', apiv1.urls),

    # REST API v2 — Django Ninja (Modul 10: API Versioning)
    # Fitur baru: Pagination, member_count pada detail course
    # Swagger UI : http://localhost:8000/api/v2/docs
    # OpenAPI    : http://localhost:8000/api/v2/openapi.json
    path('api/v2/', apiv2.urls),
]

# Modul 10 — Serve Media Files saat Development
# Memungkinkan Django serve file yang diupload user (gambar, dokumen, dll)
# di environment development (DEBUG=True).
# Di production, file media sebaiknya di-serve oleh web server (Nginx/Apache)
# atau cloud storage (AWS S3, GCS).
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
