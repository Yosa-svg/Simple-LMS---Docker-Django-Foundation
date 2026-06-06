# lms/schemas.py
"""
Schema (Pydantic) untuk REST API Django Ninja.

Schema berperan sebagai kontrak data antara client dan server:
- Input Schema  : Mendefinisikan data yang diterima dari client (request body)
- Output Schema : Mendefinisikan data yang dikembalikan ke client (response body)

Catatan adaptasi dari modul:
- Model menggunakan 'instructor' (bukan 'teacher') pada Course
- Model menggunakan 'course_id' dan 'parent_id' (ForeignKey dengan suffix _id)
- Custom User model ada di lms.User (bukan django.contrib.auth.models.User)
- Comment terhubung ke CourseMember (member_id), bukan langsung ke User

Modul 10 — Advanced API:
- CourseFilter : FilterSchema untuk filtering declaratif
- CourseUpdate : Schema PATCH (semua field Optional)
- ContentUpdate: Schema PATCH untuk CourseContent
- CourseOutV2  : Response schema v2 dengan member_count
"""

from ninja import Schema, Field, FilterSchema
from datetime import datetime
from typing import Optional, List
from django.db.models import Q


# ==============================================================================
# USER SCHEMA
# ==============================================================================

class UserOut(Schema):
    """Schema untuk data User yang dikembalikan dalam response."""
    id: int
    username: str
    first_name: str
    last_name: str
    email: str
    role: str


class Register(Schema):
    """
    Schema input untuk registrasi user baru.

    Semua field wajib diisi. Password akan di-hash otomatis
    oleh Django menggunakan create_user().
    """
    username: str
    password: str
    email: str
    first_name: str
    last_name: str
    role: str = 'student'  # Default role: student


# ==============================================================================
# CATEGORY SCHEMA
# ==============================================================================

class CategoryOut(Schema):
    """Schema untuk data Category."""
    id: int
    name: str


# ==============================================================================
# COURSE SCHEMAS
# ==============================================================================

class CourseIn(Schema):
    """Schema untuk input saat membuat/mengupdate Course."""
    name: str
    description: str = '-'
    price: int = 10000
    category_id: Optional[int] = None


class CourseOut(Schema):
    """Schema untuk output data Course (list)."""
    id: int
    name: str
    description: str
    price: int
    image: Optional[str] = None
    instructor: UserOut
    category: Optional[CategoryOut] = None
    created_at: datetime
    updated_at: datetime


class ContentTitleOut(Schema):
    """Schema ringkas untuk menampilkan judul konten saja (digunakan dalam DetailCourseOut)."""
    id: int
    name: str


class DetailCourseOut(CourseOut):
    """
    Schema untuk detail Course beserta daftar konten langsung (non-hierarki).
    Menggunakan alias karena related_name di model adalah 'coursecontent_set'
    (default Django untuk ForeignKey yang bernama course_id).
    """
    contents: List[ContentTitleOut] = Field(
        default=[],
        alias="coursecontent_set"
    )


# ==============================================================================
# MODUL 10 — FILTERING SCHEMA
# ==============================================================================

class CourseFilter(FilterSchema):
    """
    FilterSchema untuk endpoint GET /courses/.

    Setiap field yang diisi akan diterapkan sebagai kondisi WHERE di database.
    Field yang tidak diisi (None) akan diabaikan secara otomatis.

    Contoh URL:
        /api/v1/courses/?search=python
        /api/v1/courses/?min_price=50000&max_price=200000
        /api/v1/courses/?created_after=2024-01-01T00:00:00
        /api/v1/courses/?search=django&min_price=100000
    """

    # Search: mencari di field name DAN description sekaligus (OR condition)
    # q=[...] artinya FilterSchema akan membuat kondisi OR antara kedua field
    search: Optional[str] = Field(
        None,
        q=['name__icontains', 'description__icontains']
    )

    # Filter harga minimum — field custom dengan method filter_min_price()
    min_price: Optional[int] = None

    # Filter harga maksimum — field custom dengan method filter_max_price()
    max_price: Optional[int] = None

    # Filter berdasarkan tanggal dibuat — custom method filter_created_after()
    created_after: Optional[datetime] = None

    def filter_min_price(self, value: int) -> Q:
        """Custom filter: tampilkan course dengan harga >= value."""
        return Q(price__gte=value)

    def filter_max_price(self, value: int) -> Q:
        """Custom filter: tampilkan course dengan harga <= value."""
        return Q(price__lte=value)

    def filter_created_after(self, value: datetime) -> Q:
        """Custom filter: tampilkan course yang dibuat setelah tanggal ini."""
        if value:
            return Q(created_at__gt=value)
        return Q()


# ==============================================================================
# MODUL 10 — PARTIAL UPDATE SCHEMAS (PATCH)
# ==============================================================================

class CourseUpdate(Schema):
    """
    Schema untuk Partial Update Course (PATCH /courses/{id}/).

    Semua field bersifat Optional — client hanya mengirim field yang ingin diubah.
    Field yang tidak dikirim tidak akan diubah (menggunakan exclude_unset=True).

    Contoh request body untuk hanya mengubah harga:
        {"price": 80000}

    Contoh request body untuk mengubah nama dan deskripsi:
        {"name": "Kursus Python Updated", "description": "Deskripsi baru"}
    """
    name: Optional[str] = None
    description: Optional[str] = None
    price: Optional[int] = None
    category_id: Optional[int] = None


class ContentUpdate(Schema):
    """
    Schema untuk Partial Update CourseContent (PATCH /contents/{id}/).

    Semua field bersifat Optional.
    """
    name: Optional[str] = None
    description: Optional[str] = None
    video_url: Optional[str] = None


# ==============================================================================
# COURSE CONTENT SCHEMAS
# ==============================================================================

class CourseContentIn(Schema):
    """Schema untuk input saat membuat/mengupdate CourseContent."""
    name: str
    description: str = '-'
    video_url: Optional[str] = None
    course_id: int                          # ID course (wajib)
    parent_id: Optional[int] = None        # ID konten induk (opsional, untuk hierarki)


class CourseContentOut(Schema):
    """
    Schema untuk output data CourseContent.

    Catatan teknis:
    - Di model, field ForeignKey bernama 'course_id' → Django menyimpan kolomnya
      sebagai 'course_id_id' di DB. Saat serialize, kita gunakan alias untuk
      mengambil integer ID-nya.
    - Hal yang sama berlaku untuk 'parent_id' → 'parent_id_id'.
    """
    id: int
    name: str
    description: str
    video_url: Optional[str] = None
    file_attachment: Optional[str] = None  # URL file attachment (Modul 10)
    course_id: int = Field(..., alias="course_id_id")
    parent_id: Optional[int] = Field(None, alias="parent_id_id")


# ==============================================================================
# ENROLLMENT SCHEMAS (Modul 7)
# ==============================================================================

class EnrollmentOut(Schema):
    """
    Schema untuk output data Enrollment student ke course.
    Digunakan pada endpoint POST /courses/{id}/enroll/ dan GET /mycourses/
    """
    id: int
    course: CourseOut
    date_enrolled: datetime


# ==============================================================================
# COURSE MEMBER SCHEMAS (Modul 7)
# ==============================================================================

class CourseMemberOut(Schema):
    """
    Schema untuk output data CourseMember (anggota kelas dengan role).
    Digunakan untuk role std (siswa) dan ast (asisten).

    Catatan: ForeignKey bernama course_id dan user_id di model,
    sehingga Django menyimpan kolomnya sebagai course_id_id dan user_id_id.
    """
    id: int
    course_id: CourseOut = Field(..., alias="course_id")
    user_id: UserOut = Field(..., alias="user_id")
    roles: str

    class Config:
        populate_by_name = True


# ==============================================================================
# COMMENT SCHEMAS (Modul 7)
# ==============================================================================

class CommentIn(Schema):
    """
    Schema input untuk membuat komentar baru.
    User harus sudah terdaftar di course yang berisi content ini.
    """
    comment: str
    content_id: int   # ID dari CourseContent yang dikomentari


class CommentUpdate(Schema):
    """Schema input untuk mengupdate komentar yang sudah ada."""
    comment: str


class CommentOut(Schema):
    """Schema output untuk data komentar."""
    id: int
    comment: str
    content_id: int = Field(..., alias="content_id_id")
    member_id: CourseMemberOut = Field(..., alias="member_id")

    class Config:
        populate_by_name = True


# ==============================================================================
# MODUL 10 — API v2 SCHEMAS (lebih detail, dengan member_count)
# ==============================================================================

class CourseOutV2(Schema):
    """
    Schema untuk API v2 — response course yang lebih lengkap.

    Perbedaan dengan CourseOut (v1):
    - instructor: UserOut (sama, tapi bisa dikembangkan)
    - member_count: jumlah student yang enrolled (dari annotate Count)
    - created_at saja, tidak ada updated_at (disederhanakan)

    Membutuhkan annotate pada QuerySet:
        Course.objects.annotate(member_count=Count('enrollments'))
    """
    id: int
    name: str
    description: str
    price: int
    image: Optional[str] = None
    instructor: UserOut
    category: Optional[CategoryOut] = None
    member_count: int = 0         # Jumlah enrollment (dari annotate Count)
    created_at: datetime


# ==============================================================================
# GENERIC RESPONSE SCHEMAS
# ==============================================================================

class MessageOut(Schema):
    """Schema generik untuk response pesan sukses."""
    message: str


class UploadOut(Schema):
    """Schema untuk response setelah upload file berhasil (Modul 10)."""
    message: str
    filename: str
    size_kb: float
