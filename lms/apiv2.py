# lms/apiv2.py
"""
REST API v2 untuk Simple LMS — Modul 10: API Versioning.

Mengapa v2?
-----------
Ketika API sudah digunakan client (aplikasi mobile, frontend), setiap perubahan
pada struktur response bisa merusak aplikasi yang sudah ada.

API Versioning memungkinkan kita membuat versi baru tanpa merusak v1:
- Client lama tetap pakai v1 (URL: /api/v1/...)
- Client baru bisa pakai v2 (URL: /api/v2/...)

Perbedaan v2 vs v1:
-------------------
| Fitur            | v1                        | v2                                    |
|------------------|---------------------------|---------------------------------------|
| Pagination       | ❌ Flat array            | ✅ {items: [...], count: N}           |
| Page size        | —                         | 10 items per halaman                  |
| member_count     | ❌                        | ✅ Jumlah student enrolled            |
| Response format  | [...] flat list           | {items:[...], count: N} paginated     |
| Filter params    | search, min/max_price     | Sama + created_after                  |

Endpoint v2:
------------
- GET /api/v2/courses/      Daftar course (paginated, FilterSchema)
- GET /api/v2/courses/{id}/ Detail course (dengan member_count)

Swagger UI: http://localhost:8000/api/v2/docs
"""

from ninja import NinjaAPI, Query
from ninja.errors import HttpError
from ninja.pagination import paginate, PageNumberPagination
from ninja_simple_jwt.auth.ninja_auth import HttpJwtAuth
from django.db.models import Count
from typing import List

from lms.models import Course
from lms.schemas import CourseOutV2, CourseFilter


# ==============================================================================
# INSTANCE API v2
# ==============================================================================

apiv2 = NinjaAPI(
    title="Simple LMS API v2",
    version="2.0.0",
    description=(
        "API v2 untuk Simple Learning Management System. "
        "**Perbedaan utama dari v1**: "
        "Response menggunakan format paginated `{items: [...], count: N}`. "
        "Detail course menyertakan `member_count` (jumlah student enrolled). "
        "**Modul 10**: API Versioning untuk backward compatibility. "
        "Rate limiting ditangani oleh RateLimitMiddleware (20/100 req/min)."
    ),
    urls_namespace="apiv2",
    # Rate limiting: ditangani oleh lms.middleware.RateLimitMiddleware
)

# JWT auth handler (sama dengan v1)
apiAuth = HttpJwtAuth()


# ==============================================================================
# HELPER
# ==============================================================================

def get_object_or_404_v2(model, **kwargs):
    """Mengambil object dari DB, raise 404 jika tidak ditemukan."""
    try:
        return model.objects.get(**kwargs)
    except model.DoesNotExist:
        raise HttpError(404, f"{model.__name__} tidak ditemukan")


# ==============================================================================
# COURSE ENDPOINTS v2
# ==============================================================================

@apiv2.get(
    'courses/',
    response=List[CourseOutV2],
    tags=["Courses v2"],
    summary="Daftar Course (Paginated)",
    description=(
        "Mengambil daftar course dengan **pagination**. "
        "\n\n**Format response**: `{\"items\": [...], \"count\": N}` "
        "(berbeda dari v1 yang mengembalikan flat array). "
        "\n\n**Pagination**: Gunakan parameter `page` untuk berpindah halaman "
        "(default: halaman 1, 10 item per halaman). "
        "\n\n**Filter**: `search`, `min_price`, `max_price`, `created_after`. "
        "\n\n**Sorting**: `ordering` (name, -name, price, -price, created_at, -created_at). "
        "\n\n**Baru di v2**: Field `member_count` menunjukkan jumlah student yang enrolled."
    ),
)
@paginate(PageNumberPagination, page_size=10)
def listCoursesV2(
    request,
    filters: CourseFilter = Query(...),
    ordering: str = '-created_at',
):
    """
    Daftar course dengan FilterSchema + Pagination.

    Modul 10 — Pagination:
    @paginate(PageNumberPagination, page_size=10) secara otomatis:
    - Menambahkan parameter `page` ke endpoint
    - Membagi hasil menjadi halaman 10 item
    - Membungkus response dalam {"items": [...], "count": N}

    Modul 10 — FilterSchema:
    filters.filter(qs) menerapkan semua Q objects dari CourseFilter secara otomatis.

    Modul 10 — Sorting Whitelist:
    Hanya field yang ada di whitelist yang diizinkan untuk keamanan.

    Modul 10 — member_count (v2 baru):
    annotate(member_count=Count('enrollments')) menambahkan jumlah enrollment
    untuk setiap course tanpa memerlukan query tambahan (single JOIN).

    Contoh request:
        GET /api/v2/courses/?page=1
        GET /api/v2/courses/?page=2&search=python
        GET /api/v2/courses/?min_price=50000&ordering=-price&page=1
    """
    # Whitelist untuk keamanan sorting
    allowed_orderings = ['name', '-name', 'price', '-price', 'created_at', '-created_at']
    if ordering not in allowed_orderings:
        ordering = '-created_at'

    # Query dengan annotate member_count (LEFT JOIN + COUNT)
    # Ini adalah satu query, tidak ada N+1 problem
    qs = (
        Course.objects
        .select_related('instructor', 'category')
        .annotate(member_count=Count('enrollments', distinct=True))
        .all()
    )

    # Terapkan filter dari FilterSchema
    qs = filters.filter(qs)

    # Terapkan sorting
    qs = qs.order_by(ordering)

    # @paginate akan mengambil slice yang tepat berdasarkan ?page=N
    return qs


@apiv2.get(
    'courses/{id}',
    response=CourseOutV2,
    tags=["Courses v2"],
    summary="Detail Course (v2)",
    description=(
        "Mengambil detail satu course. "
        "\n\n**Baru di v2**: Field `member_count` menunjukkan jumlah student yang enrolled. "
        "Data dihitung secara real-time menggunakan Django ORM annotate."
    ),
)
def detailCourseV2(request, id: int):
    """
    Detail course versi v2 dengan member_count.

    Modul 10 — API v2:
    Perbedaan dengan v1 detailCourse:
    - Tambah annotate(member_count=Count('enrollments'))
    - Tidak ada caching Redis (v1 yang ada caching)
    - Response schema CourseOutV2 (ada field member_count)
    """
    try:
        course = (
            Course.objects
            .select_related('instructor', 'category')
            .annotate(member_count=Count('enrollments', distinct=True))
            .get(pk=id)
        )
    except Course.DoesNotExist:
        raise HttpError(404, "Course tidak ditemukan")

    return course
