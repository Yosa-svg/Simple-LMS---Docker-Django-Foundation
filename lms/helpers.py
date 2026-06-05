# lms/helpers.py
"""
Helper functions untuk Authorization pada Simple LMS API.

Prinsip DRY (Don't Repeat Yourself): fungsi-fungsi ini mengenkapsulasi
logika authorization yang berulang agar tidak tersebar di banyak endpoint.

Referensi Modul 7:
    - check_course_owner       → hanya instructor/owner yang bisa edit/delete course
    - check_owner_or_superadmin→ owner atau admin yang bisa delete comment
    - check_enrollment         → hanya user yang enroll yang bisa comment
"""

from ninja.errors import HttpError


def get_authenticated_user(request):
    """
    Mengambil objek User dari request yang sudah terautentikasi.

    Dibandingkan menggunakan request.user langsung, fungsi ini juga
    me-refresh data user dari database untuk memastikan data terkini.

    Args:
        request: Django request object (harus sudah auth=apiAuth)

    Returns:
        lms.models.User instance
    """
    from lms.models import User
    return User.objects.get(pk=request.user.id)


def check_course_owner(course, user):
    """
    Memeriksa apakah user adalah instructor/pemilik course.

    Raise HttpError 403 Forbidden jika bukan owner.
    Superadmin (is_superuser=True) selalu diizinkan.

    Args:
        course: Course instance
        user  : lms.models.User instance

    Raises:
        HttpError(403): Jika user bukan instructor course atau superadmin
    """
    if course.instructor != user and not user.is_superuser:
        raise HttpError(403, "Hanya instructor course yang dapat melakukan aksi ini")


def check_comment_owner(comment, user):
    """
    Memeriksa apakah user adalah pemilik komentar.

    Raise HttpError 403 Forbidden jika bukan owner komentar.
    Superadmin selalu diizinkan.

    Args:
        comment: Comment instance
        user   : lms.models.User instance

    Raises:
        HttpError(403): Jika user bukan pemilik komentar atau superadmin
    """
    if comment.member_id.user_id != user and not user.is_superuser:
        raise HttpError(403, "Hanya pemilik komentar yang dapat mengedit komentar ini")


def check_enrollment(user, course):
    """
    Memeriksa apakah user terdaftar (enrolled) di course tertentu.

    Mengecek tabel Enrollment. Jika tidak terdaftar, raise 403.
    Instructor course dan superadmin selalu diizinkan.

    Args:
        user  : lms.models.User instance
        course: Course instance

    Raises:
        HttpError(403): Jika user belum terdaftar di course ini
    """
    from lms.models import Enrollment
    # Superadmin dan instructor course sendiri diizinkan tanpa enrollment
    if user.is_superuser or course.instructor == user:
        return
    if not Enrollment.objects.filter(student=user, course=course).exists():
        raise HttpError(403, "Anda harus terdaftar di course ini untuk melakukan aksi ini")


def check_can_delete_comment(comment, user):
    """
    Memeriksa izin untuk menghapus komentar.

    Komentar bisa dihapus oleh:
    1. Pemilik komentar itu sendiri
    2. Instructor course yang berisi konten tersebut
    3. Superadmin

    Args:
        comment: Comment instance (harus sudah select_related content dan course)
        user   : lms.models.User instance

    Raises:
        HttpError(403): Jika user tidak memiliki izin
    """
    is_comment_owner = (comment.member_id.user_id == user)
    is_course_instructor = (comment.content_id.course_id.instructor == user)
    is_superadmin = user.is_superuser

    if not (is_comment_owner or is_course_instructor or is_superadmin):
        raise HttpError(403, "Anda tidak memiliki izin untuk menghapus komentar ini")
