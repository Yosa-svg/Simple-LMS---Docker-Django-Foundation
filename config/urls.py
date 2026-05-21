"""
URL configuration for Simple LMS project.
"""
from django.contrib import admin
from django.urls import path, include
from lms.apiv1 import apiv1

urlpatterns = [
    path('admin/', admin.site.urls),

    # Django Silk - Query Profiling Dashboard
    # Akses di: http://localhost:8000/silk/
    path('silk/', include('silk.urls', namespace='silk')),

    # Endpoint Lab - Optimasi Query (baseline vs optimized)
    path('lab/', include('lms.urls')),

    # REST API - Django Ninja (Modul 6)
    # Swagger UI : http://localhost:8000/api/v1/docs
    # OpenAPI    : http://localhost:8000/api/v1/openapi.json
    path('api/v1/', apiv1.urls),
]
