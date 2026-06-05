# lms/tasks.py
"""
Celery Async Tasks untuk Simple LMS.

Modul 9 — Asynchronous Task Processing:
    Task berjalan di latar belakang (Celery Worker), tidak memblokir HTTP response.
    Broker : RabbitMQ (menerima pesan)
    Backend: Redis    (menyimpan hasil task)

Tasks yang tersedia:

    TRIGGERED TASKS (dipanggil oleh endpoint):
    ──────────────────────────────────────────
    send_enrollment_email    : Email konfirmasi enrollment ke student
    generate_certificate     : Generate sertifikat (saat course selesai)
    export_course_report     : Generate CSV report untuk instructor

    SCHEDULED TASKS (dijalankan secara terjadwal oleh Celery Beat):
    ────────────────────────────────────────────────────────────────
    update_course_statistics : Update enrollment count di cache (setiap jam)

Cara test task secara manual:
    docker-compose exec app python manage.py shell
    >>> from lms.tasks import send_enrollment_email
    >>> result = send_enrollment_email.delay(user_id=1, course_id=1)
    >>> result.get()   # Tunggu sampai selesai dan ambil hasilnya

Monitor task di Flower: http://localhost:5555
"""

import csv
import io
import logging
from datetime import datetime

from celery import shared_task
from django.core.mail import send_mail
from django.conf import settings

logger = logging.getLogger(__name__)


# ==============================================================================
# TRIGGERED TASKS — Dipanggil oleh endpoint
# ==============================================================================

@shared_task(
    name='lms.tasks.send_enrollment_email',
    bind=True,
    max_retries=3,
    default_retry_delay=60,  # Retry setelah 60 detik jika gagal
)
def send_enrollment_email(self, user_id: int, course_id: int):
    """
    Mengirim email konfirmasi enrollment ke student.

    Dipanggil setelah student berhasil enroll ke course.
    Berjalan async — tidak memblokir HTTP response.

    Retry policy: 3 kali percobaan dengan jeda 60 detik.

    Args:
        user_id  : ID student yang enroll
        course_id: ID course yang di-enroll

    Returns:
        dict: Status pengiriman email
    """
    try:
        from lms.models import User, Course
        user = User.objects.get(pk=user_id)
        course = Course.objects.select_related('instructor').get(pk=course_id)

        subject = f"✅ Konfirmasi Enrollment: {course.name}"
        message = (
            f"Halo {user.first_name or user.username},\n\n"
            f"Selamat! Anda berhasil mendaftar ke course:\n\n"
            f"  📚 {course.name}\n"
            f"  👨‍🏫 Instructor: {course.instructor.get_full_name() or course.instructor.username}\n"
            f"  💰 Harga: Rp {course.price:,}\n\n"
            f"Selamat belajar!\n\n"
            f"Salam,\nTim Simple LMS"
        )

        send_mail(
            subject=subject,
            message=message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[user.email],
            fail_silently=False,
        )

        logger.info(f"[Task] send_enrollment_email: Email sent to {user.email} for course '{course.name}'")
        return {
            'status': 'success',
            'email': user.email,
            'course': course.name,
            'sent_at': datetime.now().isoformat(),
        }

    except Exception as exc:
        logger.error(f"[Task] send_enrollment_email failed: {exc}")
        # Retry dengan exponential backoff
        raise self.retry(exc=exc)


@shared_task(
    name='lms.tasks.generate_certificate',
    bind=True,
    max_retries=2,
)
def generate_certificate(self, user_id: int, course_id: int):
    """
    Generate sertifikat penyelesaian course.

    Dipanggil ketika student menyelesaikan semua lesson dalam course.
    Dalam implementasi ini, simulasi dengan menyimpan data ke MongoDB.

    Args:
        user_id  : ID student
        course_id: ID course yang diselesaikan

    Returns:
        dict: Data sertifikat yang di-generate
    """
    try:
        from lms.models import User, Course
        from lms.mongo_logger import log_activity

        user = User.objects.get(pk=user_id)
        course = Course.objects.get(pk=course_id)

        # Simulasi generate certificate (dalam production: gunakan ReportLab/WeasyPrint)
        certificate_data = {
            'certificate_id': f"CERT-{user_id}-{course_id}-{int(datetime.now().timestamp())}",
            'student_name': user.get_full_name() or user.username,
            'course_name': course.name,
            'issued_at': datetime.now().isoformat(),
            'issued_by': 'Simple LMS',
        }

        # Simpan ke MongoDB sebagai record
        log_activity(
            action='certificate_issued',
            resource=f'course:{course_id}',
            user_id=user_id,
            username=user.username,
            metadata=certificate_data,
        )

        # Kirim email dengan nomor sertifikat
        send_mail(
            subject=f"🎓 Sertifikat Course: {course.name}",
            message=(
                f"Selamat {user.first_name or user.username}!\n\n"
                f"Anda telah menyelesaikan course '{course.name}'.\n\n"
                f"Nomor Sertifikat: {certificate_data['certificate_id']}\n\n"
                f"Salam,\nTim Simple LMS"
            ),
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[user.email],
            fail_silently=True,
        )

        logger.info(f"[Task] generate_certificate: {certificate_data['certificate_id']}")
        return certificate_data

    except Exception as exc:
        logger.error(f"[Task] generate_certificate failed: {exc}")
        raise self.retry(exc=exc)


@shared_task(
    name='lms.tasks.export_course_report',
    bind=True,
    max_retries=1,
)
def export_course_report(self, course_id: int, requested_by_user_id: int):
    """
    Generate laporan CSV untuk course tertentu secara async.

    Berisi data: daftar student enrolled, progress, tanggal enrollment.
    Dalam production, file CSV akan disimpan ke cloud storage dan link
    dikirim via email. Di sini, kita simulate dengan return data CSV string.

    Args:
        course_id             : ID course yang akan di-export
        requested_by_user_id  : ID user (instructor) yang request report

    Returns:
        dict: {'status': str, 'rows': int, 'csv_preview': str}
    """
    try:
        from lms.models import Course, Enrollment

        course = Course.objects.get(pk=course_id)
        enrollments = (
            Enrollment.objects
            .filter(course=course)
            .select_related('student')
        )

        # Build CSV
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(['Student ID', 'Username', 'Full Name', 'Email', 'Date Enrolled'])

        for enrollment in enrollments:
            student = enrollment.student
            writer.writerow([
                student.id,
                student.username,
                student.get_full_name(),
                student.email,
                enrollment.date_enrolled.strftime('%Y-%m-%d %H:%M'),
            ])

        csv_content = output.getvalue()
        row_count = enrollments.count()

        logger.info(f"[Task] export_course_report: {row_count} rows for course:{course_id}")
        return {
            'status': 'success',
            'course_id': course_id,
            'course_name': course.name,
            'rows': row_count,
            'generated_at': datetime.now().isoformat(),
            'csv_preview': csv_content[:500] + ('...' if len(csv_content) > 500 else ''),
        }

    except Exception as exc:
        logger.error(f"[Task] export_course_report failed: {exc}")
        raise self.retry(exc=exc)


# ==============================================================================
# SCHEDULED TASKS — Dijalankan secara periodik oleh Celery Beat
# ==============================================================================

@shared_task(name='lms.tasks.update_course_statistics')
def update_course_statistics():
    """
    Update statistik enrollment course dan simpan ke Redis cache.

    Dijadwalkan setiap jam oleh Celery Beat.
    Berguna untuk dashboard analytics yang tidak perlu real-time.

    Schedule dikonfigurasi via Django Admin → Periodic Tasks
    (setelah migrate django_celery_beat).

    Returns:
        dict: Ringkasan statistik yang diupdate
    """
    try:
        from lms.models import Course, Enrollment
        from django.core.cache import cache

        stats = {}
        courses = Course.objects.all()

        for course in courses:
            count = Enrollment.objects.filter(course=course).count()
            stats[course.id] = {
                'course_name': course.name,
                'enrollment_count': count,
            }
            # Cache per course dengan key 'course_stats:{id}'
            cache.set(f'course_stats:{course.id}', count, timeout=3600)  # 1 jam

        # Cache summary semua course
        cache.set('all_course_stats', stats, timeout=3600)

        total_enrollments = sum(s['enrollment_count'] for s in stats.values())
        logger.info(
            f"[Task] update_course_statistics: Updated {len(stats)} courses, "
            f"total enrollments: {total_enrollments}"
        )
        return {
            'status': 'success',
            'courses_updated': len(stats),
            'total_enrollments': total_enrollments,
            'updated_at': datetime.now().isoformat(),
        }

    except Exception as exc:
        logger.error(f"[Task] update_course_statistics failed: {exc}")
        return {'status': 'error', 'error': str(exc)}
