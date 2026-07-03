"""
urls.py - URL Routes untuk Lab Optimasi Query

Semua endpoint dikelompokkan dalam prefix /lab/ (di-include dari config/urls.py)

Pasang 1 — Course + Instructor:
  /lab/course-list/baseline/   → N+1 Problem (untuk di-profil dengan Silk)
  /lab/course-list/optimized/  → select_related

Pasang 2 — Course + Members + Konten + Komentar:
  /lab/course-members/baseline/   → N+1 berlapis
  /lab/course-members/optimized/  → prefetch_related chain + annotate

Pasang 3 — Statistik Dashboard Dosen:
  /lab/course-dashboard/baseline/   → aggregate terpisah + loop Python
  /lab/course-dashboard/optimized/  → aggregate() + annotate() gabungan

Cara akses setelah server berjalan:
  http://localhost:8000/lab/course-list/baseline/
  http://localhost:8000/lab/course-list/optimized/
  http://localhost:8000/lab/course-members/baseline/
  http://localhost:8000/lab/course-members/optimized/
  http://localhost:8000/lab/course-dashboard/baseline/
  http://localhost:8000/lab/course-dashboard/optimized/

Dashboard Silk:
  http://localhost:8000/silk/
"""

from django.urls import path
from . import views

urlpatterns = [
    # ── Pasang 1: Daftar Course + Instructor ──────────────────────────────────
    path('course-list/baseline/',   views.course_list_baseline,   name='course-list-baseline'),
    path('course-list/optimized/',  views.course_list_optimized,  name='course-list-optimized'),

    # ── Pasang 2: Daftar Course + Members + Konten + Komentar ─────────────────
    path('course-members/baseline/',  views.course_members_baseline,  name='course-members-baseline'),
    path('course-members/optimized/', views.course_members_optimized, name='course-members-optimized'),

    # ── Pasang 3: Statistik Dashboard Dosen ───────────────────────────────────
    path('course-dashboard/baseline/',  views.course_dashboard_baseline,  name='course-dashboard-baseline'),
    path('course-dashboard/optimized/', views.course_dashboard_optimized, name='course-dashboard-optimized'),
]
