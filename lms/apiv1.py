# lms/apiv1.py
"""
REST API untuk Simple LMS menggunakan Django Ninja.

Endpoint yang tersedia:
    Course:
        GET    /api/v1/courses/         - List semua course (+ filter & search)
        GET    /api/v1/courses/{id}     - Detail course beserta kontennya
        POST   /api/v1/courses/         - Buat course baru
        PUT    /api/v1/courses/{id}     - Update course
        DELETE /api/v1/courses/{id}     - Hapus course

    CourseContent:
        GET    /api/v1/contents/        - List semua konten (+ filter per course)
        GET    /api/v1/contents/{id}    - Detail satu konten
        POST   /api/v1/contents/        - Buat konten baru
        PUT    /api/v1/contents/{id}    - Update konten
        DELETE /api/v1/contents/{id}   - Hapus konten

Dokumentasi interaktif (Swagger UI): http://localhost:8000/api/v1/docs
OpenAPI JSON                        : http://localhost:8000/api/v1/openapi.json

Catatan: Autentikasi dan otorisasi akan dibahas di Modul 7.
         Pada modul ini, semua endpoint bersifat publik (tanpa login).
"""

from ninja import NinjaAPI
from ninja.errors import HttpError
from django.db import IntegrityError
from typing import List, Optional

from lms.models import Course, CourseContent
from lms.schemas import (
    CourseIn, CourseOut, DetailCourseOut,
    CourseContentIn, CourseContentOut,
)


# ==============================================================================
# INSTANCE API UTAMA
# ==============================================================================

apiv1 = NinjaAPI(
    title="Simple LMS API",
    version="1.0.0",
    description=(
        "API untuk Simple Learning Management System. "
        "Dokumentasi ini di-generate otomatis oleh Django Ninja."
    ),
)


# ==============================================================================
# HELPER FUNCTION
# ==============================================================================

def get_object_or_404(model, **kwargs):
    """
    Mengambil satu object dari database.
    Raise HttpError 404 jika tidak ditemukan.

    Mengurangi boilerplate try-except pada setiap endpoint.
    """
    try:
        return model.objects.get(**kwargs)
    except model.DoesNotExist:
        model_name = model.__name__
        raise HttpError(404, f"{model_name} tidak ditemukan")


# ==============================================================================
# COURSE ENDPOINTS
# ==============================================================================

@apiv1.get(
    'courses/',
    response=List[CourseOut],
    tags=["Courses"],
    summary="Daftar Course",
    description=(
        "Mengambil daftar semua course yang tersedia beserta data pengajar (instructor) "
        "dan kategori. Gunakan query parameter untuk filter, pencarian, dan sorting."
    ),
)
def listCourses(
    request,
    search: Optional[str] = None,
    min_price: Optional[int] = None,
    max_price: Optional[int] = None,
    ordering: str = '-created_at',
):
    """
    Mengambil daftar semua course.

    Query parameters:
    - search    : Cari berdasarkan nama course (case-insensitive)
    - min_price : Harga minimum
    - max_price : Harga maksimum
    - ordering  : Urutan hasil (default: -created_at / terbaru)
    """
    qs = Course.objects.select_related('instructor', 'category').all()

    if search:
        qs = qs.filter(name__icontains=search)
    if min_price is not None:
        qs = qs.filter(price__gte=min_price)
    if max_price is not None:
        qs = qs.filter(price__lte=max_price)

    return qs.order_by(ordering)


@apiv1.get(
    'courses/{id}',
    response=DetailCourseOut,
    tags=["Courses"],
    summary="Detail Course",
    description="Mengambil detail satu course beserta daftar semua kontennya.",
)
def detailCourse(request, id: int):
    """Mengambil detail course beserta daftar kontennya."""
    try:
        return (
            Course.objects
            .prefetch_related('coursecontent_set')
            .select_related('instructor', 'category')
            .get(pk=id)
        )
    except Course.DoesNotExist:
        raise HttpError(404, "Course tidak ditemukan")


@apiv1.post(
    'courses/',
    response={201: CourseOut},
    tags=["Courses"],
    summary="Buat Course",
    description=(
        "Membuat course baru. "
        "Catatan: instructor sementara di-hardcode ke user pertama dengan role 'instructor'. "
        "Akan diganti dengan autentikasi pada Modul 7."
    ),
)
def createCourse(request, data: CourseIn):
    """
    Membuat course baru.

    Field yang diperlukan:
    - name        : Nama course (wajib)
    - description : Deskripsi course (default: '-')
    - price       : Harga course (default: 10000)
    - category_id : ID kategori (opsional)
    """
    from lms.models import User

    # Sementara hardcode instructor → user pertama dengan role 'instructor'
    # Autentikasi nyata akan diimplementasikan di Modul 7
    instructor = User.objects.filter(role='instructor').first()
    if not instructor:
        # Fallback: gunakan user pertama apapun role-nya
        instructor = User.objects.first()
    if not instructor:
        raise HttpError(400, "Belum ada user di database. Jalankan fixtures terlebih dahulu.")

    course = Course.objects.create(
        name=data.name,
        description=data.description,
        price=data.price,
        category_id=data.category_id,
        instructor=instructor,
    )
    return 201, course


@apiv1.put(
    'courses/{id}',
    response=CourseOut,
    tags=["Courses"],
    summary="Update Course",
    description="Mengupdate seluruh data course berdasarkan ID.",
)
def updateCourse(request, id: int, data: CourseIn):
    """Mengupdate data course secara keseluruhan (PUT)."""
    course = get_object_or_404(Course, pk=id)

    course.name = data.name
    course.description = data.description
    course.price = data.price
    course.category_id = data.category_id
    course.save()

    # Refresh relasi setelah update agar response lengkap
    return Course.objects.select_related('instructor', 'category').get(pk=course.pk)


@apiv1.delete(
    'courses/{id}',
    response={204: None},
    tags=["Courses"],
    summary="Hapus Course",
    description="Menghapus course berdasarkan ID.",
)
def deleteCourse(request, id: int):
    """Menghapus course."""
    course = get_object_or_404(Course, pk=id)

    try:
        course.delete()
        return 204, None
    except Exception:
        raise HttpError(
            400,
            "Course tidak bisa dihapus karena masih memiliki member, konten, atau enrollment."
        )


# ==============================================================================
# COURSE CONTENT ENDPOINTS
# ==============================================================================

@apiv1.get(
    'contents/',
    response=List[CourseContentOut],
    tags=["Contents"],
    summary="Daftar Konten",
    description=(
        "Mengambil daftar semua konten kelas. "
        "Gunakan query parameter course_id untuk memfilter per course."
    ),
)
def listContents(
    request,
    course_id: Optional[int] = None,
    search: Optional[str] = None,
):
    """
    Mengambil daftar semua konten kelas.

    Query parameters:
    - course_id : Filter konten berdasarkan ID course
    - search    : Cari berdasarkan nama konten (case-insensitive)
    """
    qs = CourseContent.objects.select_related('course_id', 'parent_id').all()

    if course_id is not None:
        qs = qs.filter(course_id=course_id)
    if search:
        qs = qs.filter(name__icontains=search)

    return qs


@apiv1.get(
    'contents/{id}',
    response=CourseContentOut,
    tags=["Contents"],
    summary="Detail Konten",
    description="Mengambil detail satu konten berdasarkan ID.",
)
def detailContent(request, id: int):
    """Mengambil detail konten berdasarkan ID."""
    return get_object_or_404(CourseContent, pk=id)


@apiv1.post(
    'contents/',
    response={201: CourseContentOut},
    tags=["Contents"],
    summary="Buat Konten",
    description="Membuat konten kelas baru.",
)
def createContent(request, data: CourseContentIn):
    """
    Membuat konten baru.

    Field yang diperlukan:
    - name        : Judul konten (wajib)
    - description : Deskripsi (default: '-')
    - video_url   : URL video (opsional)
    - course_id   : ID course (wajib)
    - parent_id   : ID konten induk untuk hierarki (opsional)
    """
    # Validasi: pastikan course dengan course_id tersebut ada
    course = get_object_or_404(Course, pk=data.course_id)

    # Validasi: pastikan parent_id valid jika diberikan
    parent = None
    if data.parent_id is not None:
        parent = get_object_or_404(CourseContent, pk=data.parent_id)

    try:
        content = CourseContent.objects.create(
            name=data.name,
            description=data.description,
            video_url=data.video_url,
            course_id=course,
            parent_id=parent,
        )
        return 201, content
    except IntegrityError:
        raise HttpError(409, "Konten sudah ada atau terjadi konflik data.")


@apiv1.put(
    'contents/{id}',
    response=CourseContentOut,
    tags=["Contents"],
    summary="Update Konten",
    description="Mengupdate seluruh data konten berdasarkan ID.",
)
def updateContent(request, id: int, data: CourseContentIn):
    """Mengupdate data konten secara keseluruhan (PUT)."""
    content = get_object_or_404(CourseContent, pk=id)

    # Validasi course baru
    course = get_object_or_404(Course, pk=data.course_id)

    # Validasi parent baru
    parent = None
    if data.parent_id is not None:
        parent = get_object_or_404(CourseContent, pk=data.parent_id)

    content.name = data.name
    content.description = data.description
    content.video_url = data.video_url
    content.course_id = course
    content.parent_id = parent
    content.save()

    return content


@apiv1.delete(
    'contents/{id}',
    response={204: None},
    tags=["Contents"],
    summary="Hapus Konten",
    description="Menghapus konten berdasarkan ID.",
)
def deleteContent(request, id: int):
    """Menghapus konten."""
    content = get_object_or_404(CourseContent, pk=id)

    try:
        content.delete()
        return 204, None
    except Exception:
        raise HttpError(
            400,
            "Konten tidak bisa dihapus karena masih memiliki sub-konten atau komentar."
        )
