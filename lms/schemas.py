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
"""

from ninja import Schema, Field
from datetime import datetime
from typing import Optional, List


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
    course_id: int = Field(..., alias="course_id_id")
    parent_id: Optional[int] = Field(None, alias="parent_id_id")

