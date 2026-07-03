"""
views.py - Endpoint Lab: Baseline vs Optimized Query

Berisi 3 pasang endpoint untuk perbandingan performa di Django Silk:

  Pasang 1 — Daftar Course + Instructor (Teacher)
    GET /lab/course-list/baseline/   → N+1 Problem
    GET /lab/course-list/optimized/  → select_related

  Pasang 2 — Daftar Course + Members + Konten + Jumlah Komentar
    GET /lab/course-members/baseline/   → N+1 berlapis
    GET /lab/course-members/optimized/  → prefetch_related chain

  Pasang 3 — Statistik Dashboard Dosen
    GET /lab/course-dashboard/baseline/   → aggregate terpisah + loop
    GET /lab/course-dashboard/optimized/  → aggregate + annotate gabungan

Petunjuk Lab:
  1. Akses setiap endpoint *baseline* → cek Silk (query count, waktu)
  2. Akses setiap endpoint *optimized* → cek Silk kembali
  3. Bandingkan hasil di http://localhost:8000/silk/
"""

from django.http import JsonResponse
from django.db.models import Count, Avg, Max, Min, Sum, Q, F

from .models import Course, CourseMember, CourseContent, Comment


# ══════════════════════════════════════════════════════════════════════════════
# PASANG 1 — Daftar Course + Instructor (Teacher)
# ══════════════════════════════════════════════════════════════════════════════

def course_list_baseline(request):
    """
    ❌ BASELINE — Daftar course + nama instructor

    N+1 Problem:
      - 1 query  : SELECT * FROM lms_course
      - N queries : SELECT * FROM lms_user WHERE id = ? (per course!)
    Dengan 100 course → 101 queries.

    Endpoint: GET /lab/course-list/baseline/
    """
    courses = Course.objects.all()   # Hanya 1 query, TAPI...
    data = []
    for c in courses:
        data.append({
            'id': c.id,
            'course': c.name,
            'price': c.price,
            # ↓ Setiap akses c.instructor menembak query BARU ke DB!
            'instructor': c.instructor.username,
            'instructor_name': f"{c.instructor.first_name} {c.instructor.last_name}",
        })
    return JsonResponse({'total': len(data), 'data': data})


def course_list_optimized(request):
    """
    ✅ OPTIMIZED — Daftar course + nama instructor

    Solusi: select_related('instructor')
      - SQL JOIN: 1 query tunggal mengambil course + instructor sekaligus
    Dengan 100 course → tetap 1 query.

    Endpoint: GET /lab/course-list/optimized/
    """
    # select_related('instructor') → SQL INNER JOIN lms_user ON instructor_id
    # Juga include 'category' sesuai custom manager for_listing()
    courses = Course.objects.select_related('instructor', 'category').all()
    data = []
    for c in courses:
        data.append({
            'id': c.id,
            'course': c.name,
            'price': c.price,
            # ↓ Data sudah di-cache dari JOIN — tidak ada query tambahan!
            'instructor': c.instructor.username,
            'instructor_name': f"{c.instructor.first_name} {c.instructor.last_name}",
            'category': c.category.name if c.category else None,
        })
    return JsonResponse({'total': len(data), 'data': data})


# ══════════════════════════════════════════════════════════════════════════════
# PASANG 2 — Daftar Course + Members + Konten + Jumlah Komentar
# ══════════════════════════════════════════════════════════════════════════════

def course_members_baseline(request):
    """
    ❌ BASELINE — Course + daftar member + jumlah konten + jumlah komentar

    N+1 berlapis:
      - 1 query       : SELECT courses
      - N queries     : SELECT members per course
      - N queries     : SELECT contents per course
      - N*M queries   : SELECT comments per content
    Dengan 100 courses, 5 contents/course, 10 comments/content → ribuan queries!

    Endpoint: GET /lab/course-members/baseline/
    """
    courses = Course.objects.all()
    data = []
    for c in courses:
        # ↓ Query terpisah untuk setiap course → N+1
        members = CourseMember.objects.filter(course_id=c)
        contents = CourseContent.objects.filter(course_id=c)

        content_list = []
        for content in contents:
            # ↓ Query terpisah per konten → N*M queries!
            comment_count = Comment.objects.filter(content_id=content).count()
            content_list.append({
                'content_name': content.name,
                'comment_count': comment_count,
            })

        data.append({
            'id': c.id,
            'course': c.name,
            # ↓ Query lagi untuk instructor
            'instructor': c.instructor.username,
            'member_count': members.count(),
            'members': [m.user_id.username for m in members],  # N+1 pada user!
            'contents': content_list,
        })
    return JsonResponse({'total': len(data), 'data': data})


def course_members_optimized(request):
    """
    ✅ OPTIMIZED — Course + daftar member + jumlah konten + jumlah komentar

    Solusi: select_related + prefetch_related chain + annotate
      - select_related('instructor')          → JOIN instructor (1 query)
      - prefetch_related('coursemember_set')  → semua members (1 query terpisah)
      - prefetch_related('coursemember_set__user_id')  → user per member
      - prefetch_related('coursecontent_set') → semua contents (1 query)
      - annotate(member_count, content_count) → hitung di DB

    Total: ~4 queries, berapapun jumlah course.

    Endpoint: GET /lab/course-members/optimized/
    """
    from django.db.models import Prefetch

    courses = Course.objects.select_related(
        'instructor',
        'category',
    ).prefetch_related(
        # Prefetch member beserta data user-nya sekaligus
        Prefetch(
            'coursemember_set',
            queryset=CourseMember.objects.select_related('user_id')
        ),
        # Prefetch content beserta jumlah komentar via annotate
        Prefetch(
            'coursecontent_set',
            queryset=CourseContent.objects.annotate(
                comment_count=Count('comment')
            )
        ),
    ).annotate(
        member_count=Count('coursemember', distinct=True),
        content_count=Count('coursecontent', distinct=True),
    ).all()

    data = []
    for c in courses:
        # Semua data sudah di-cache → ZERO extra queries!
        content_list = []
        for content in c.coursecontent_set.all():
            content_list.append({
                'content_name': content.name,
                'comment_count': content.comment_count,  # Dari annotate
            })

        data.append({
            'id': c.id,
            'course': c.name,
            'instructor': c.instructor.username,     # Dari select_related
            'category': c.category.name if c.category else None,
            'member_count': c.member_count,          # Dari annotate
            'content_count': c.content_count,        # Dari annotate
            'members': [m.user_id.username for m in c.coursemember_set.all()],  # Dari prefetch
            'contents': content_list,
        })
    return JsonResponse({'total': len(data), 'data': data})


# ══════════════════════════════════════════════════════════════════════════════
# PASANG 3 — Statistik Dashboard Dosen
# ══════════════════════════════════════════════════════════════════════════════

def course_dashboard_baseline(request):
    """
    ❌ BASELINE — Statistik dashboard dosen

    Masalah:
      - Banyak query aggregate terpisah
      - Menghitung dalam loop Python (sangat tidak efisien)
      - Untuk setiap course: query members, query contents, query comments

    Endpoint: GET /lab/course-dashboard/baseline/
    """
    courses = Course.objects.all()

    # Query 1: hitung total
    total_courses = courses.count()

    # Query 2: harga tertinggi
    max_price = 0
    for c in courses:              # Loop Python — BURUK
        if c.price > max_price:
            max_price = c.price

    # Query 3: harga terendah
    min_price = float('inf')
    for c in courses:              # Loop lagi — BURUK
        if c.price < min_price:
            min_price = c.price

    # Menghitung member count per course — N queries!
    course_stats = []
    for c in courses:
        member_count = CourseMember.objects.filter(course_id=c).count()    # N query
        content_count = CourseContent.objects.filter(course_id=c).count()  # N query
        comment_count = Comment.objects.filter(
            content_id__course_id=c
        ).count()  # N query lagi

        course_stats.append({
            'course': c.name,
            'price': c.price,
            'instructor': c.instructor.username,  # N query untuk instructor!
            'member_count': member_count,
            'content_count': content_count,
            'comment_count': comment_count,
        })

    # Query: rata-rata harga
    total_price = sum(c['price'] for c in course_stats)
    avg_price = total_price / len(course_stats) if course_stats else 0

    return JsonResponse({
        'summary': {
            'total_courses': total_courses,
            'max_price': max_price,
            'min_price': min_price,
            'avg_price': round(avg_price, 2),
        },
        'courses': course_stats,
    })


def course_dashboard_optimized(request):
    """
    ✅ OPTIMIZED — Statistik dashboard dosen

    Solusi:
      - aggregate() → semua statistik global dalam 1 query
      - annotate()  → per-course stats tanpa loop → 1 query
      - select_related('instructor') → tidak ada extra query
    Total: 2 queries, berapapun jumlah course.

    Endpoint: GET /lab/course-dashboard/optimized/
    """
    # ── Query 1: Semua statistik global sekaligus ─────────────────────────────
    # Satu SQL: SELECT MAX, MIN, AVG, COUNT, SUM sekaligus
    stats = Course.objects.aggregate(
        total_courses=Count('id'),
        max_price=Max('price'),
        min_price=Min('price'),
        avg_price=Avg('price'),
        total_revenue=Sum('price'),
        # Hitung student (role std) dan asisten (role ast) secara conditional
        total_students=Count(
            'coursemember',
            filter=Q(coursemember__roles='std'),
            distinct=True
        ),
        total_assistants=Count(
            'coursemember',
            filter=Q(coursemember__roles='ast'),
            distinct=True
        ),
    )

    # ── Query 2: Per-course stats dengan annotate ─────────────────────────────
    # SQL: SELECT course.*, COUNT(members), COUNT(contents), COUNT(comments)
    #      FROM course
    #      LEFT JOIN coursemember ...
    #      LEFT JOIN coursecontent ...
    #      LEFT JOIN comment ...
    #      GROUP BY course.id
    courses = Course.objects.select_related(
        'instructor', 'category'
    ).annotate(
        member_count=Count('coursemember', distinct=True),
        content_count=Count('coursecontent', distinct=True),
        student_count=Count(
            'coursemember',
            filter=Q(coursemember__roles='std'),
            distinct=True
        ),
        assistant_count=Count(
            'coursemember',
            filter=Q(coursemember__roles='ast'),
            distinct=True
        ),
        comment_count=Count(
            'coursecontent__comment',
            distinct=True
        ),
    ).order_by('-member_count')   # Urutkan by popularitas

    course_stats = []
    for c in courses:
        course_stats.append({
            'course': c.name,
            'price': c.price,
            'instructor': c.instructor.username,     # Dari select_related
            'category': c.category.name if c.category else None,
            'member_count': c.member_count,          # Dari annotate
            'content_count': c.content_count,        # Dari annotate
            'student_count': c.student_count,        # Dari conditional annotate
            'assistant_count': c.assistant_count,    # Dari conditional annotate
            'comment_count': c.comment_count,        # Dari annotate
        })

    return JsonResponse({
        'summary': {
            'total_courses': stats['total_courses'],
            'max_price': stats['max_price'],
            'min_price': stats['min_price'],
            'avg_price': round(stats['avg_price'] or 0, 2),
            'total_revenue': stats['total_revenue'],
            'total_students': stats['total_students'],
            'total_assistants': stats['total_assistants'],
        },
        'courses': course_stats,
    })
