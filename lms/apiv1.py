# lms/apiv1.py
"""
REST API untuk Simple LMS menggunakan Django Ninja.

Modul 7 — JWT Authentication & Authorization:
    - POST /api/v1/auth/sign-in         Login & dapatkan JWT token
    - POST /api/v1/auth/token-refresh   Refresh access token
    - POST /api/v1/register/            Daftar user baru
    - GET  /api/v1/profile/             Profil user yang sedang login

Modul 7 — Enrollment & Komentar (Protected):
    - POST /api/v1/courses/{id}/enroll/ Enroll ke course
    - GET  /api/v1/mycourses/           Daftar course yang saya ikuti
    - POST /api/v1/comments/            Post komentar (harus enrolled)
    - PUT  /api/v1/comments/{id}/       Update komentar (hanya owner)
    - DELETE /api/v1/comments/{id}/     Hapus komentar (owner/instructor/admin)

Course Endpoints (Protected untuk write operations):
    - GET    /api/v1/courses/           Daftar course (FilterSchema + Redis cache)
    - GET    /api/v1/courses/{id}       Detail course (+ Redis cache)
    - POST   /api/v1/courses/           Buat course (auth required)
    - PUT    /api/v1/courses/{id}       Update course (owner/admin only)
    - PATCH  /api/v1/courses/{id}       Partial update course (Modul 10)
    - DELETE /api/v1/courses/{id}       Hapus course (owner/admin only)

Content Endpoints:
    - GET    /api/v1/contents/          Daftar konten
    - GET    /api/v1/contents/{id}      Detail konten
    - POST   /api/v1/contents/          Buat konten (auth required)
    - PUT    /api/v1/contents/{id}      Update konten (auth required)
    - PATCH  /api/v1/contents/{id}      Partial update konten (Modul 10)
    - DELETE /api/v1/contents/{id}      Hapus konten (auth required)

Modul 9 — Advanced:
    - Redis caching pada GET /courses/ dan GET /courses/{id}
    - Rate limiting via Django Ninja throttling (Modul 10)
    - Celery tasks dipanggil saat enrollment
    - MongoDB activity logging

Modul 10 — Advanced API Features:
    - POST /api/v1/courses/{id}/upload-image/         Upload thumbnail course
    - POST /api/v1/contents/{id}/upload-attachment/   Upload file materi
    - GET  /api/v1/contents/{id}/download/            Download file materi
    - FilterSchema pada GET /courses/ (search, min_price, max_price, created_after)
    - Partial Update PATCH pada Course dan Content
    - Rate Limiting: 20 req/min (anon), 100 req/min (auth)

Modul 12 — Message Brokers & Async Tasks:
    - POST /api/v1/reports/generate/{id}/    Trigger report course (Celery task)
    - GET  /api/v1/reports/status/{task_id}/ Cek status task via AsyncResult
    - generate_daily_stats                    Periodic: statistik harian pukul 00:00
    - cleanup_old_logs                        Periodic: cleanup log pukul 02:00

Dokumentasi interaktif (Swagger UI): http://localhost:8000/api/v1/docs
OpenAPI JSON                        : http://localhost:8000/api/v1/openapi.json
"""

from ninja import NinjaAPI, Query, File, UploadedFile
from ninja.errors import HttpError
from ninja_simple_jwt.auth.views.api import mobile_auth_router
from ninja_simple_jwt.auth.ninja_auth import HttpJwtAuth
from django.db import IntegrityError
from django.http import FileResponse
from typing import List, Optional
from celery.result import AsyncResult

from lms.models import Course, CourseContent, Enrollment, CourseMember, Comment, User
from lms.schemas import (
    CourseIn, CourseOut, DetailCourseOut,
    CourseUpdate, ContentUpdate,
    CourseFilter,
    CourseContentIn, CourseContentOut,
    Register, UserOut,
    EnrollmentOut,
    CommentIn, CommentUpdate, CommentOut, MessageOut,
    UploadOut,
)
from lms.helpers import (
    get_authenticated_user,
    check_course_owner,
    check_comment_owner,
    check_enrollment,
    check_can_delete_comment,
)
from lms.cache import (
    get_cached_course_list,
    set_course_list_cache,
    get_cached_course_detail,
    set_course_detail_cache,
    invalidate_course_cache,
    check_rate_limit,
    increment_course_popularity,
    get_popular_courses,
)
from lms.mongo_logger import log_activity, log_enrollment, log_course_view


# ==============================================================================
# INSTANCE API UTAMA
# ==============================================================================

apiv1 = NinjaAPI(
    title="Simple LMS API",
    version="1.0.0",
    description=(
        "API untuk Simple Learning Management System. "
        "Modul 7: JWT Authentication & Authorization. "
        "Modul 9: Redis Caching, MongoDB Logs, Celery Tasks. "
        "Modul 10: Filtering, Rate Limiting (Middleware), File Upload. "
        "Dokumentasi ini di-generate otomatis oleh Django Ninja."
    ),
    # Rate limiting ditangani oleh lms.middleware.RateLimitMiddleware
    # (20 req/min anon, 100 req/min auth) — tidak perlu throttle parameter di sini
)

# ==============================================================================
# MODUL 7 — JWT Authentication Setup
# Register auth router dari ninja-simple-jwt.
# Menyediakan endpoint:
#   POST /api/v1/auth/sign-in         → Login, return access + refresh token
#   POST /api/v1/auth/token-refresh   → Refresh access token
# ==============================================================================

apiv1.add_router("/auth/", mobile_auth_router, tags=["Auth"])

# JWT auth handler — tambahkan sebagai parameter auth=apiAuth pada endpoint
# yang memerlukan authentication.
apiAuth = HttpJwtAuth()


# ==============================================================================
# HELPER FUNCTION INTERNAL
# ==============================================================================

def get_object_or_404(model, **kwargs):
    """
    Mengambil satu object dari database.
    Raise HttpError 404 jika tidak ditemukan.
    """
    try:
        return model.objects.get(**kwargs)
    except model.DoesNotExist:
        model_name = model.__name__
        raise HttpError(404, f"{model_name} tidak ditemukan")


def get_client_ip(request) -> str:
    """Mengambil IP address client dari request."""
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        return x_forwarded_for.split(',')[0].strip()
    return request.META.get('REMOTE_ADDR', '0.0.0.0')


def validate_file_upload(file: UploadedFile, max_size_mb: int, allowed_types: list) -> None:
    """
    Modul 10 — Validasi file upload.

    Memeriksa ukuran dan tipe MIME file.
    Raise HttpError 400 jika validasi gagal.

    Args:
        file: File yang diupload
        max_size_mb: Ukuran maksimal dalam MB
        allowed_types: List tipe MIME yang diizinkan
    """
    if file.size > max_size_mb * 1024 * 1024:
        raise HttpError(400, f"Ukuran file maksimal {max_size_mb}MB. File Anda: {file.size / 1024 / 1024:.1f}MB")

    if file.content_type not in allowed_types:
        allowed_str = ', '.join(allowed_types)
        raise HttpError(400, f"Tipe file tidak diizinkan. Gunakan: {allowed_str}")


# ==============================================================================
# MODUL 7 — USER REGISTRATION & PROFILE
# ==============================================================================

@apiv1.post(
    'register/',
    response={201: UserOut},
    tags=["Auth"],
    summary="Registrasi User Baru",
    description=(
        "Mendaftarkan user baru. Password akan di-hash secara otomatis oleh Django. "
        "Role default adalah 'student'. Pastikan username dan email belum digunakan."
    ),
    auth=None,  # Endpoint publik — tidak perlu login
)
def register(request, data: Register):
    """
    Mendaftarkan user baru.

    Validasi:
    - Username harus unik
    - Email harus unik
    - Password di-hash otomatis dengan create_user()
    """
    # Cek duplikasi username
    if User.objects.filter(username=data.username).exists():
        raise HttpError(400, "Username sudah digunakan")

    # Cek duplikasi email
    if User.objects.filter(email=data.email).exists():
        raise HttpError(400, "Email sudah digunakan")

    # Buat user baru — create_user() otomatis hash password
    new_user = User.objects.create_user(
        username=data.username,
        password=data.password,
        email=data.email,
        first_name=data.first_name,
        last_name=data.last_name,
        role=data.role,
    )

    # Log ke MongoDB
    log_activity(
        action='register',
        resource=f'user:{new_user.id}',
        user_id=new_user.id,
        username=new_user.username,
    )

    return 201, new_user


@apiv1.get(
    'profile/',
    response=UserOut,
    auth=apiAuth,
    tags=["Auth"],
    summary="Profil Saya",
    description="Mengambil data profil user yang sedang login (berdasarkan JWT token).",
)
def get_profile(request):
    """Mengambil profil user yang sedang login."""
    user = get_authenticated_user(request)
    log_activity('view_profile', f'user:{user.id}', user_id=user.id, username=user.username)
    return user


# ==============================================================================
# COURSE ENDPOINTS (Modul 7 + Modul 9 + Modul 10 + Modul 12)
# ==============================================================================

@apiv1.get(
    'courses/popular/',
    response=List[CourseOut],
    tags=["Courses"],
    summary="Top Courses (Popular)",
    description=(
        "Mengambil 10 course terpopuler berdasarkan jumlah enrollment. "
        "**Modul 12**: Menggunakan Redis Sorted Set."
    ),
)
def getPopularCourses(request, limit: int = 10):
    """Mengambil top N courses terpopuler dari Redis Sorted Set."""
    popular_data = get_popular_courses(limit)
    
    # Jika redis kosong/baru, sync dari DB
    if not popular_data:
        from lms.cache import sync_popularity_from_db
        sync_popularity_from_db()
        popular_data = get_popular_courses(limit)
        
    course_ids = [cid for cid, score in popular_data]
    
    if not course_ids:
        return []
        
    # Ambil courses dari DB (tetap jaga urutan dari redis)
    courses = Course.objects.select_related('instructor', 'category').filter(id__in=course_ids)
    course_dict = {c.id: c for c in courses}
    
    ordered_courses = [course_dict[cid] for cid in course_ids if cid in course_dict]
    return ordered_courses


@apiv1.get(
    'courses/',
    response=List[CourseOut],
    tags=["Courses"],
    summary="Daftar Course",
    description=(
        "Mengambil daftar semua course. "
        "**Modul 9**: Response di-cache di Redis selama 5 menit untuk query tanpa filter. "
        "**Modul 10**: Menggunakan FilterSchema untuk filtering declaratif. "
        "Filter: `search`, `min_price`, `max_price`, `created_after`. "
        "Sorting: `ordering` (name, -name, price, -price, created_at, -created_at). "
        "Cache di-invalidate otomatis saat ada perubahan course."
    ),
)
def listCourses(
    request,
    filters: CourseFilter = Query(...),
    ordering: str = '-created_at',
):
    """
    Mengambil daftar semua course dengan filtering dan sorting.

    Modul 9 — Redis Caching:
    - Cache-aside pattern: cek cache dulu, jika miss → ambil DB → simpan ke cache
    - Cache hanya aktif untuk query tanpa filter (default listing)

    Modul 10 — FilterSchema:
    - search      : Cari di name DAN description (OR, case-insensitive)
    - min_price   : Harga minimum (inklusif)
    - max_price   : Harga maksimum (inklusif)
    - created_after: Hanya course yang dibuat setelah tanggal ini

    Modul 10 — Sorting Whitelist (keamanan):
    - Whitelist mencegah user menginput field arbitrary ke order_by()
    """
    # Whitelist field yang boleh digunakan untuk sorting
    allowed_orderings = ['name', '-name', 'price', '-price', 'created_at', '-created_at']
    if ordering not in allowed_orderings:
        ordering = '-created_at'  # Fallback ke default jika input tidak valid

    # Caching hanya untuk request tanpa filter (halaman utama)
    # Cek apakah semua filter kosong dengan memeriksa dict filter
    filter_data = filters.dict(exclude_none=True, exclude_unset=True)
    # Hapus key 'search' jika kosong string
    filter_data = {k: v for k, v in filter_data.items() if v is not None and v != ''}
    use_cache = len(filter_data) == 0 and ordering == '-created_at'

    if use_cache:
        cached = get_cached_course_list()
        if cached is not None:
            return cached  # Cache HIT

    # Cache MISS atau ada filter — ambil dari database
    qs = Course.objects.select_related('instructor', 'category').all()

    # Modul 10: Terapkan FilterSchema (Q objects otomatis)
    qs = filters.filter(qs)

    # Terapkan sorting (sudah divalidasi dengan whitelist)
    result = list(qs.order_by(ordering))

    # Simpan ke cache hanya jika tidak ada filter
    if use_cache:
        set_course_list_cache(result)

    return result


@apiv1.get(
    'courses/{id}',
    response=DetailCourseOut,
    tags=["Courses"],
    summary="Detail Course",
    description=(
        "Mengambil detail satu course beserta daftar semua kontennya. "
        "**Modul 9**: Response di-cache di Redis selama 10 menit."
    ),
)
def detailCourse(request, id: int):
    """
    Mengambil detail course beserta daftar kontennya.

    Modul 9 — Redis Caching:
    - Cache key: 'simplelms:course_detail:{id}'
    - TTL: 10 menit
    """
    # Cek cache terlebih dahulu
    cached = get_cached_course_detail(id)
    if cached is not None:
        return cached  # Cache HIT

    # Cache MISS — ambil dari database
    try:
        course = (
            Course.objects
            .prefetch_related('coursecontent_set')
            .select_related('instructor', 'category')
            .get(pk=id)
        )
    except Course.DoesNotExist:
        raise HttpError(404, "Course tidak ditemukan")

    # Simpan ke cache
    set_course_detail_cache(id, course)

    # Log view ke MongoDB (hanya jika ada user yang login)
    if hasattr(request, 'user') and request.user and request.user.is_authenticated:
        log_course_view(request.user.id, request.user.username, id)

    return course


@apiv1.post(
    'courses/{id}/visit/',
    response={200: dict},
    tags=["Courses"],
    summary="Catat Kunjungan Course",
    description=(
        "Mencatat riwayat kunjungan ke course menggunakan Redis Session. "
        "**Modul 12**: Tidak memerlukan login, menggunakan browser session."
    ),
)
def visitCourse(request, id: int):
    """Mencatat ID course yang dikunjungi ke dalam session."""
    course = get_object_or_404(Course, pk=id)
    
    # Ambil history yang sudah ada dari session (list of IDs)
    history = request.session.get('course_history', [])
    
    # Jika ID sudah ada, hapus dari posisi lama (untuk ditaruh di awal/paling baru)
    if id in history:
        history.remove(id)
        
    # Tambahkan di depan
    history.insert(0, id)
    
    # Batasi maksimal 20 history
    history = history[:20]
    
    # Simpan kembali ke session
    request.session['course_history'] = history
    request.session.modified = True  # Tandai ada perubahan agar disimpan
    
    return 200, {"message": f"Kunjungan ke course '{course.name}' dicatat", "history": history}


@apiv1.get(
    'my-history/',
    response=List[CourseOut],
    tags=["Courses"],
    summary="Riwayat Kunjungan Saya",
    description=(
        "Mengambil daftar course yang pernah dikunjungi di session ini. "
        "**Modul 12**: Menggunakan Redis Session."
    ),
)
def getMyHistory(request):
    """Mengambil history kunjungan dari session dan mengembalikan data coursenya."""
    history = request.session.get('course_history', [])
    
    if not history:
        return []
        
    courses = Course.objects.select_related('instructor', 'category').filter(id__in=history)
    course_dict = {c.id: c for c in courses}
    
    # Jaga urutan sesuai array di session
    ordered_courses = [course_dict[cid] for cid in history if cid in course_dict]
    return ordered_courses


@apiv1.post(
    'courses/',
    response={201: CourseOut},
    auth=apiAuth,
    tags=["Courses"],
    summary="Buat Course",
    description=(
        "Membuat course baru. User yang membuat otomatis menjadi instructor. "
        "Memerlukan authentication (JWT token). "
        "Hanya user dengan role 'instructor' atau 'admin' yang bisa membuat course."
    ),
)
def createCourse(request, data: CourseIn):
    """
    Membuat course baru.

    Authorization: User yang terautentikasi otomatis menjadi instructor.
    Modul 9: Invalidate cache course list setelah course baru dibuat.
    """
    user = get_authenticated_user(request)

    course = Course.objects.create(
        name=data.name,
        description=data.description,
        price=data.price,
        category_id=data.category_id,
        instructor=user,
    )

    # Invalidate cache — daftar course berubah
    invalidate_course_cache()

    # Log ke MongoDB
    log_activity(
        'create_course', f'course:{course.id}',
        user_id=user.id, username=user.username,
        metadata={'course_name': course.name},
    )

    return 201, Course.objects.select_related('instructor', 'category').get(pk=course.pk)


@apiv1.put(
    'courses/{id}',
    response=CourseOut,
    auth=apiAuth,
    tags=["Courses"],
    summary="Update Course (Full)",
    description=(
        "Mengupdate seluruh data course (PUT — semua field wajib). "
        "Untuk mengupdate sebagian field saja, gunakan PATCH. "
        "**Authorization**: Hanya instructor course atau superadmin yang bisa mengedit."
    ),
)
def updateCourse(request, id: int, data: CourseIn):
    """
    Mengupdate data course secara keseluruhan (PUT).

    Authorization check: check_course_owner() → raise 403 jika bukan owner.
    Modul 9: Invalidate cache course list dan detail setelah update.
    """
    user = get_authenticated_user(request)
    course = get_object_or_404(Course, pk=id)

    # Authorization: hanya instructor course atau superadmin
    check_course_owner(course, user)

    course.name = data.name
    course.description = data.description
    course.price = data.price
    course.category_id = data.category_id
    course.save()

    # Invalidate cache — data course berubah
    invalidate_course_cache(course_id=id)

    log_activity('update_course', f'course:{id}', user_id=user.id, username=user.username)

    return Course.objects.select_related('instructor', 'category').get(pk=course.pk)


@apiv1.patch(
    'courses/{id}',
    response=CourseOut,
    auth=apiAuth,
    tags=["Courses"],
    summary="Partial Update Course (PATCH)",
    description=(
        "Mengupdate **sebagian** field course. Hanya field yang dikirim yang akan diubah. "
        "Field yang tidak dikirim tetap tidak berubah. "
        "**Modul 10**: Menggunakan `exclude_unset=True` pada schema PATCH. "
        "**Authorization**: Hanya instructor course atau superadmin. "
        "\n\nContoh: `{\"price\": 99000}` hanya mengubah harga, tanpa menyentuh name/description."
    ),
)
def patchCourse(request, id: int, data: CourseUpdate):
    """
    Partial update course (PATCH).

    Modul 10 — PATCH vs PUT:
    - PUT  : Kirim SEMUA field (replace seluruh resource)
    - PATCH: Kirim hanya field yang ingin diubah (partial update)

    Kunci implementasi: data.dict(exclude_unset=True)
    - Tanpa exclude_unset: {"name": null, "price": 99000} → name jadi null
    - Dengan exclude_unset: {"price": 99000} → hanya price yang berubah
    """
    user = get_authenticated_user(request)
    course = get_object_or_404(Course, pk=id)

    # Authorization: hanya instructor course atau superadmin
    check_course_owner(course, user)

    # Update hanya field yang benar-benar dikirim oleh client
    # exclude_unset=True = abaikan field yang tidak ada dalam request body
    updated_fields = data.dict(exclude_unset=True)
    for attr, value in updated_fields.items():
        setattr(course, attr, value)

    course.save()

    # Invalidate cache — data course berubah
    invalidate_course_cache(course_id=id)

    log_activity('patch_course', f'course:{id}', user_id=user.id, username=user.username,
                 metadata={'updated_fields': list(updated_fields.keys())})

    return Course.objects.select_related('instructor', 'category').get(pk=course.pk)


@apiv1.delete(
    'courses/{id}',
    response={204: None},
    auth=apiAuth,
    tags=["Courses"],
    summary="Hapus Course",
    description=(
        "Menghapus course berdasarkan ID. "
        "**Authorization**: Hanya instructor course atau superadmin yang bisa menghapus."
    ),
)
def deleteCourse(request, id: int):
    """
    Menghapus course.

    Authorization: hanya instructor course atau superadmin.
    Modul 9: Invalidate cache setelah course dihapus.
    """
    user = get_authenticated_user(request)
    course = get_object_or_404(Course, pk=id)

    # Authorization: hanya instructor course atau superadmin
    check_course_owner(course, user)

    try:
        course.delete()
        # Invalidate cache
        invalidate_course_cache(course_id=id)
        log_activity('delete_course', f'course:{id}', user_id=user.id, username=user.username)
        return 204, None
    except Exception:
        raise HttpError(
            400,
            "Course tidak bisa dihapus karena masih memiliki member, konten, atau enrollment."
        )


# ==============================================================================
# MODUL 10 — FILE UPLOAD: COURSE IMAGE
# ==============================================================================

@apiv1.post(
    'courses/{id}/upload-image/',
    response=UploadOut,
    auth=apiAuth,
    tags=["Courses"],
    summary="Upload Gambar Course",
    description=(
        "Mengupload gambar thumbnail untuk course. "
        "**Format yang diizinkan**: JPEG, PNG, WebP. "
        "**Ukuran maksimal**: 2MB. "
        "**Authorization**: Hanya instructor course yang bisa upload. "
        "\n\nFile disimpan di `/media/course_images/`. "
        "URL gambar bisa diakses melalui field `image` di response detail course."
    ),
)
def uploadCourseImage(request, id: int, file: UploadedFile = File(...)):
    """
    Upload gambar thumbnail course.

    Modul 10 — File Upload:
    - Validasi ukuran: maks 2MB
    - Validasi tipe: image/jpeg, image/png, image/webp
    - Simpan ke model.image (ImageField → upload_to='course_images/')
    - Authorization: hanya instructor pemilik course
    """
    user = get_authenticated_user(request)
    course = get_object_or_404(Course, pk=id)

    # Authorization: hanya instructor pemilik course
    check_course_owner(course, user)

    # Validasi file
    validate_file_upload(
        file,
        max_size_mb=2,
        allowed_types=['image/jpeg', 'image/png', 'image/webp', 'image/jpg']
    )

    # Hapus gambar lama jika ada (optional: bersihkan storage)
    if course.image:
        try:
            course.image.delete(save=False)
        except Exception:
            pass  # Abaikan jika file lama tidak bisa dihapus

    # Simpan file baru ke model
    course.image = file
    course.save()

    # Invalidate cache — gambar course berubah
    invalidate_course_cache(course_id=id)

    log_activity('upload_course_image', f'course:{id}', user_id=user.id, username=user.username,
                 metadata={'filename': file.name})

    return {
        "message": f"Gambar course '{course.name}' berhasil diupload.",
        "filename": file.name,
        "size_kb": round(file.size / 1024, 2),
    }


# ==============================================================================
# ENROLLMENT ENDPOINTS (Modul 7)
# ==============================================================================

@apiv1.post(
    'courses/{id}/enroll/',
    response={201: EnrollmentOut},
    auth=apiAuth,
    tags=["Enrollment"],
    summary="Enroll ke Course",
    description=(
        "Mendaftarkan diri ke sebuah course. "
        "Satu student hanya bisa enroll satu kali per course (unique constraint). "
        "**Modul 9**: Setelah enroll, Celery task `send_enrollment_email` dipanggil secara async."
    ),
)
def courseEnrollment(request, id: int):
    """
    Mendaftarkan user yang sedang login ke course.

    Modul 9:
    - Setelah enroll berhasil, trigger Celery task untuk kirim email
    - Log enrollment ke MongoDB
    """
    user = get_authenticated_user(request)
    course = get_object_or_404(Course, pk=id)

    # Cek duplikasi enrollment
    if Enrollment.objects.filter(student=user, course=course).exists():
        raise HttpError(400, "Anda sudah terdaftar di course ini")

    enrollment = Enrollment.objects.create(student=user, course=course)

    # Modul 9 — Trigger Celery task async (tidak memblokir response)
    try:
        from lms.tasks import send_enrollment_email
        send_enrollment_email.delay(user_id=user.id, course_id=course.id)
    except Exception:
        pass  # Jangan gagalkan enrollment jika Celery tidak tersedia

    # Modul 9 — Log ke MongoDB
    log_enrollment(user.id, user.username, course.id, course.name)

    # Modul 12 — Increment popularity (Sorted Set)
    increment_course_popularity(course.id)

    return 201, enrollment


@apiv1.get(
    'mycourses/',
    response=List[EnrollmentOut],
    auth=apiAuth,
    tags=["Enrollment"],
    summary="Course Saya",
    description="Mengambil daftar semua course yang saya ikuti (enrolled).",
)
def getMyCourses(request):
    """Mengambil daftar course yang diikuti user yang sedang login."""
    user = get_authenticated_user(request)
    enrollments = (
        Enrollment.objects
        .filter(student=user)
        .select_related('course', 'course__instructor', 'course__category')
    )
    return list(enrollments)


# ==============================================================================
# COMMENT ENDPOINTS (Modul 7)
# ==============================================================================

@apiv1.post(
    'comments/',
    response={201: MessageOut},
    auth=apiAuth,
    tags=["Comments"],
    summary="Post Komentar",
    description=(
        "Membuat komentar baru pada konten kelas. "
        "**Authorization**: User harus terdaftar (enrolled) di course yang berisi konten ini. "
        "Instructor course dan superadmin selalu bisa berkomentar."
    ),
)
def postComment(request, data: CommentIn):
    """
    Membuat komentar baru.

    Authorization flow:
    1. Ambil user dari JWT token
    2. Cari CourseContent berdasarkan content_id
    3. Cek apakah user sudah enroll di course yang berisi konten ini
    4. Buat CourseMember entry (jika belum ada) atau gunakan yang ada
    5. Simpan Comment
    """
    user = get_authenticated_user(request)

    content = CourseContent.objects.select_related('course_id').filter(id=data.content_id).first()
    if content is None:
        raise HttpError(404, "Konten tidak ditemukan")

    course = content.course_id

    # Authorization: cek enrollment (instructor & superadmin dikecualikan di helper)
    check_enrollment(user, course)

    # Cari atau buat CourseMember untuk user ini
    # CourseMember digunakan oleh model Comment sebagai FK
    member, _ = CourseMember.objects.get_or_create(
        course_id=course,
        user_id=user,
        defaults={'roles': 'std'},
    )

    Comment.objects.create(
        comment=data.comment,
        content_id=content,
        member_id=member,
    )

    log_activity('post_comment', f'content:{data.content_id}', user_id=user.id, username=user.username)

    return 201, {"message": "Komentar berhasil ditambahkan"}


@apiv1.put(
    'comments/{id}',
    response=MessageOut,
    auth=apiAuth,
    tags=["Comments"],
    summary="Update Komentar",
    description=(
        "Mengupdate komentar yang sudah ada. "
        "**Authorization**: Hanya pemilik komentar atau superadmin yang bisa mengedit."
    ),
)
def updateComment(request, id: int, data: CommentUpdate):
    """
    Mengupdate komentar.

    Authorization: hanya pemilik komentar atau superadmin.
    """
    user = get_authenticated_user(request)

    comment = Comment.objects.select_related('member_id__user_id').filter(id=id).first()
    if comment is None:
        raise HttpError(404, "Komentar tidak ditemukan")

    # Authorization: hanya pemilik komentar atau superadmin
    check_comment_owner(comment, user)

    comment.comment = data.comment
    comment.save()

    log_activity('update_comment', f'comment:{id}', user_id=user.id, username=user.username)

    return {"message": "Komentar berhasil diperbarui"}


@apiv1.delete(
    'comments/{id}',
    response=MessageOut,
    auth=apiAuth,
    tags=["Comments"],
    summary="Hapus Komentar",
    description=(
        "Menghapus komentar. "
        "**Authorization**: "
        "Pemilik komentar, instructor course yang berisi konten tersebut, atau superadmin."
    ),
)
def deleteComment(request, id: int):
    """
    Menghapus komentar.

    Authorization: pemilik komentar ATAU instructor course ATAU superadmin.
    """
    user = get_authenticated_user(request)

    comment = (
        Comment.objects
        .select_related('member_id__user_id', 'content_id__course_id__instructor')
        .filter(id=id)
        .first()
    )
    if comment is None:
        raise HttpError(404, "Komentar tidak ditemukan")

    # Authorization: cek siapa yang boleh hapus
    check_can_delete_comment(comment, user)

    comment.delete()
    log_activity('delete_comment', f'comment:{id}', user_id=user.id, username=user.username)

    return {"message": "Komentar berhasil dihapus"}


# ==============================================================================
# COURSE CONTENT ENDPOINTS (Modul 10: + PATCH + Upload + Download)
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
    auth=apiAuth,
    tags=["Contents"],
    summary="Buat Konten",
    description="Membuat konten kelas baru. Memerlukan authentication.",
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
    auth=apiAuth,
    tags=["Contents"],
    summary="Update Konten (Full)",
    description=(
        "Mengupdate seluruh data konten berdasarkan ID (PUT). "
        "Untuk update sebagian field, gunakan PATCH /contents/{id}/."
    ),
)
def updateContent(request, id: int, data: CourseContentIn):
    """Mengupdate data konten secara keseluruhan (PUT)."""
    content = get_object_or_404(CourseContent, pk=id)
    course = get_object_or_404(Course, pk=data.course_id)

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


@apiv1.patch(
    'contents/{id}',
    response=CourseContentOut,
    auth=apiAuth,
    tags=["Contents"],
    summary="Partial Update Konten (PATCH)",
    description=(
        "Mengupdate **sebagian** field konten. Hanya field yang dikirim yang berubah. "
        "**Modul 10**: Partial update menggunakan `exclude_unset=True`. "
        "**Authorization**: Hanya instructor course yang bisa mengupdate konten. "
        "\n\nContoh: `{\"video_url\": \"https://...\"}`  hanya mengubah URL video."
    ),
)
def patchContent(request, id: int, data: ContentUpdate):
    """
    Partial update konten kelas (PATCH).

    Modul 10: Hanya field yang dikirim yang diubah.
    """
    user = get_authenticated_user(request)

    content = CourseContent.objects.select_related('course_id').filter(id=id).first()
    if content is None:
        raise HttpError(404, "Konten tidak ditemukan")

    # Authorization: hanya instructor pemilik course
    course = content.course_id
    check_course_owner(course, user)

    # Update hanya field yang dikirim
    updated_fields = data.dict(exclude_unset=True)
    for attr, value in updated_fields.items():
        setattr(content, attr, value)

    content.save()

    log_activity('patch_content', f'content:{id}', user_id=user.id, username=user.username,
                 metadata={'updated_fields': list(updated_fields.keys())})

    return content


@apiv1.delete(
    'contents/{id}',
    response={204: None},
    auth=apiAuth,
    tags=["Contents"],
    summary="Hapus Konten",
    description="Menghapus konten berdasarkan ID. Memerlukan authentication.",
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


# ==============================================================================
# MODUL 10 — FILE UPLOAD: CONTENT ATTACHMENT
# ==============================================================================

@apiv1.post(
    'contents/{id}/upload-attachment/',
    response=UploadOut,
    auth=apiAuth,
    tags=["Contents"],
    summary="Upload File Materi",
    description=(
        "Mengupload file materi (attachment) untuk konten kelas. "
        "**Format yang diizinkan**: PDF, DOC, DOCX, PPT, PPTX, ZIP, MP4, PNG, JPG. "
        "**Ukuran maksimal**: 10MB. "
        "**Authorization**: Hanya instructor course yang bisa upload. "
        "\n\nFile disimpan di `/media/content_files/`. "
        "Gunakan endpoint `/contents/{id}/download/` untuk mendownload file ini."
    ),
)
def uploadContentAttachment(request, id: int, file: UploadedFile = File(...)):
    """
    Upload file attachment untuk konten kelas.

    Modul 10 — File Upload:
    - Validasi ukuran: maks 10MB
    - Validasi tipe: berbagai format dokumen, media, dan archive
    - Simpan ke model.file_attachment (FileField → upload_to='content_files/')
    - Authorization: hanya instructor pemilik course
    """
    user = get_authenticated_user(request)

    content = CourseContent.objects.select_related('course_id').filter(id=id).first()
    if content is None:
        raise HttpError(404, "Konten tidak ditemukan")

    # Authorization: hanya instructor pemilik course
    course = content.course_id
    check_course_owner(course, user)

    # Validasi file
    allowed_types = [
        'application/pdf',
        'application/msword',
        'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
        'application/vnd.ms-powerpoint',
        'application/vnd.openxmlformats-officedocument.presentationml.presentation',
        'application/zip',
        'video/mp4',
        'image/jpeg',
        'image/png',
    ]
    validate_file_upload(file, max_size_mb=10, allowed_types=allowed_types)

    # Hapus file lama jika ada
    if content.file_attachment:
        try:
            content.file_attachment.delete(save=False)
        except Exception:
            pass

    # Simpan file baru
    content.file_attachment = file
    content.save()

    log_activity('upload_attachment', f'content:{id}', user_id=user.id, username=user.username,
                 metadata={'filename': file.name, 'size': file.size})

    return {
        "message": f"File materi '{content.name}' berhasil diupload.",
        "filename": file.name,
        "size_kb": round(file.size / 1024, 2),
    }


# ==============================================================================
# MODUL 10 — FILE DOWNLOAD: CONTENT ATTACHMENT
# ==============================================================================

@apiv1.get(
    'contents/{id}/download/',
    tags=["Contents"],
    summary="Download File Materi",
    description=(
        "Mendownload file materi (attachment) dari konten kelas. "
        "**Authorization**: User harus terdaftar (enrolled) di course yang berisi konten ini. "
        "Instructor dan superadmin selalu bisa download. "
        "\n\nResponse: File stream dengan header `Content-Disposition: attachment`."
    ),
    auth=apiAuth,
)
def downloadAttachment(request, id: int):
    """
    Download file attachment dari konten kelas.

    Modul 10 — File Download:
    - Authorization: user harus enrolled di course (atau instructor/superadmin)
    - Return FileResponse dengan as_attachment=True (force download)
    - Filename diambil dari path file (basename saja)
    """
    user = get_authenticated_user(request)

    content = CourseContent.objects.select_related('course_id__instructor').filter(id=id).first()
    if content is None:
        raise HttpError(404, "Konten tidak ditemukan")

    # Cek apakah file ada
    if not content.file_attachment:
        raise HttpError(404, "Konten ini tidak memiliki file attachment.")

    course = content.course_id

    # Authorization: harus enrolled ATAU instructor ATAU superadmin
    is_instructor = (course.instructor == user)
    is_superadmin = user.is_superuser

    if not (is_instructor or is_superadmin):
        # Cek enrollment
        is_enrolled = Enrollment.objects.filter(student=user, course=course).exists()
        if not is_enrolled:
            raise HttpError(403, "Anda harus terdaftar di course ini untuk mendownload materi.")

    # Ambil nama file dari path (hanya basename)
    filename = content.file_attachment.name.split('/')[-1]

    log_activity('download_attachment', f'content:{id}', user_id=user.id, username=user.username,
                 metadata={'filename': filename})

    return FileResponse(
        content.file_attachment.open('rb'),
        as_attachment=True,
        filename=filename,
    )


# ==============================================================================
# MODUL 9 — ANALYTICS & MONITORING ENDPOINTS
# ==============================================================================

@apiv1.get(
    'analytics/my-activity/',
    auth=apiAuth,
    tags=["Analytics"],
    summary="Aktivitas Saya",
    description=(
        "Mengambil history aktivitas user yang sedang login dari MongoDB. "
        "**Modul 9**: Data diambil dari MongoDB activity_logs collection."
    ),
)
def getMyActivity(request, limit: int = 20):
    """
    Mengambil history aktivitas user dari MongoDB.

    Modul 9 — MongoDB:
    Query ke collection activity_logs, filter berdasarkan user_id,
    sort berdasarkan timestamp descending.
    """
    user = get_authenticated_user(request)
    from lms.mongo_logger import get_user_activity
    activities = get_user_activity(user.id, limit=limit)
    return activities


@apiv1.get(
    'analytics/enrollment-stats/',
    auth=apiAuth,
    tags=["Analytics"],
    summary="Statistik Enrollment",
    description=(
        "Mengambil statistik enrollment dari MongoDB menggunakan aggregation pipeline. "
        "**Modul 9**: MongoDB aggregation query untuk analytics."
    ),
)
def getEnrollmentStats(request):
    """
    Statistik enrollment menggunakan MongoDB aggregation.

    Modul 9 — MongoDB Aggregation:
    Menggunakan $group pipeline untuk menghitung enrollment per course.
    """
    from lms.mongo_logger import get_enrollment_stats
    return get_enrollment_stats()


@apiv1.get(
    'analytics/popular-courses/',
    tags=["Analytics"],
    summary="Course Terpopuler",
    description=(
        "Mengambil daftar course terpopuler berdasarkan jumlah views dari MongoDB. "
        "**Modul 11**: Menggunakan MongoDB aggregation pipeline ($match, $group, $sort)."
    ),
)
def getPopularCourses(request, limit: int = 5):
    """
    Modul 11 — MongoDB Aggregation:
    Pipeline: $match view_course → $group by course → $addFields unique_count → $sort → $limit
    """
    from lms.mongo_logger import get_popular_courses
    return get_popular_courses(limit=limit)


@apiv1.post(
    'analytics/log/',
    auth=apiAuth,
    tags=["Analytics"],
    summary="Catat Aktivitas Manual",
    description=(
        "Mencatat aktivitas user ke MongoDB activity_logs secara manual. "
        "**Modul 11**: Demonstrasi insert dokumen ke MongoDB dari Django API."
    ),
)
def logActivity(request, action: str, course_id: int = None, metadata: dict = None):
    """
    Modul 11 — Insert dokumen ke MongoDB.
    Gunakan untuk mencatat aktivitas custom dari client.
    """
    from lms.mongo_logger import log_activity
    user = get_authenticated_user(request)
    log_activity(
        action=action,
        resource=f'course:{course_id}' if course_id else 'manual',
        user_id=user.id,
        username=user.username,
        metadata={
            'course_id': course_id,
            **(metadata or {}),
        },
    )
    return {'status': 'logged', 'action': action}


@apiv1.get(
    'analytics/daily-summary/',
    tags=["Analytics"],
    summary="Ringkasan Aktivitas Harian",
    description=(
        "Mengambil ringkasan aktivitas harian dari MongoDB. "
        "**Modul 11**: Menggunakan $dateToString dan $group untuk agregasi per hari."
    ),
)
def getDailySummary(request, days: int = 7):
    """
    Modul 11 — MongoDB Aggregation:
    Group berdasarkan tanggal menggunakan $dateToString untuk N hari terakhir.
    """
    from lms.mongo_logger import get_daily_activity_summary
    return get_daily_activity_summary(days=days)


@apiv1.post(
    'courses/{id}/export-report/',
    auth=apiAuth,
    tags=["Analytics"],
    summary="Export Report Course",
    description=(
        "Memicu export laporan CSV course secara async. "
        "**Authorization**: Hanya instructor course atau superadmin. "
        "**Modul 9**: Menggunakan Celery task `export_course_report` yang berjalan di background."
    ),
)
def exportCourseReport(request, id: int):
    """
    Trigger async export CSV report untuk course.

    Modul 9 — Celery:
    Task berjalan di background, tidak memblokir response.
    Monitor progress di Flower: http://localhost:5555
    """
    user = get_authenticated_user(request)
    course = get_object_or_404(Course, pk=id)

    # Authorization: hanya instructor course atau superadmin
    check_course_owner(course, user)

    try:
        from lms.tasks import export_course_report
        task = export_course_report.delay(
            course_id=course.id,
            requested_by_user_id=user.id,
        )
        return {
            "message": "Export report sedang diproses di background.",
            "task_id": task.id,
            "course": course.name,
            "monitor_url": f"http://localhost:5555/task/{task.id}",
        }
    except Exception as e:
        raise HttpError(500, f"Gagal memulai export task: {str(e)}")


# ==============================================================================
# REPORT GENERATION ENDPOINTS (Modul 12 — Trigger & Poll Pattern)
# ==============================================================================

@apiv1.post(
    'reports/generate/{id}/',
    auth=apiAuth,
    tags=["Analytics"],
    summary="Generate Report Course (Async)",
    description=(
        "Memicu pembuatan laporan statistik course secara asynchronous. "
        "Mengembalikan `task_id` yang dapat digunakan untuk melacak progres via "
        "`GET /reports/status/{task_id}/`. "
        "**Modul 12**: Demonstrasi pola Trigger-and-Poll dengan Celery."
    ),
)
def generateReport(request, id: int):
    """
    Trigger pembuatan laporan course secara async.

    Modul 12 — Alur Trigger-and-Poll:
        1. POST /reports/generate/{id}/     → dapat task_id (langsung)
        2. GET  /reports/status/{task_id}/ → polling sampai status SUCCESS
    """
    user = get_authenticated_user(request)
    course = get_object_or_404(Course, pk=id)

    # Authorization: hanya instructor atau superadmin
    check_course_owner(course, user)

    try:
        from lms.tasks import generate_course_report
        task = generate_course_report.delay(course_id=course.id)
        return {
            "task_id": task.id,
            "status": "processing",
            "message": f"Report untuk course '{course.name}' sedang dibuat di background.",
            "poll_url": f"/api/v1/reports/status/{task.id}/",
        }
    except Exception as e:
        raise HttpError(500, f"Gagal memulai task: {str(e)}")


@apiv1.get(
    'reports/status/{task_id}/',
    auth=apiAuth,
    tags=["Analytics"],
    summary="Cek Status Report Task",
    description=(
        "Mengecek status task Celery berdasarkan `task_id`. "
        "Status: PENDING, STARTED, SUCCESS, FAILURE. "
        "**Modul 12**: Demonstrasi AsyncResult untuk status polling."
    ),
)
def reportStatus(request, task_id: str):
    """
    Cek status task Celery berdasarkan task_id.

    Modul 12 — AsyncResult:
    - PENDING   : Task belum diambil worker / task_id tidak dikenal
    - STARTED   : Worker sedang mengeksekusi
    - SUCCESS   : Task berhasil, field 'result' berisi datanya
    - FAILURE   : Task gagal, field 'error' berisi pesan error
    """
    result = AsyncResult(task_id)

    response = {
        "task_id": task_id,
        "status": result.status,
    }

    if result.ready():
        if result.successful():
            response["result"] = result.result
        else:
            response["error"] = str(result.result)  # Exception message
    else:
        response["message"] = "Task masih dalam proses..."

    return response
