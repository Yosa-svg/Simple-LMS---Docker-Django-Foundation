from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from .models import (
    User, Category, Course, Lesson, Enrollment, Progress,
    CourseMember, CourseContent, Comment
)


# ==============================================================================
# USER ADMIN
# ==============================================================================

@admin.register(User)
class UserAdmin(BaseUserAdmin):
    """Admin konfigurasi untuk Custom User Model."""
    list_display = ('username', 'email', 'first_name', 'last_name', 'role', 'is_staff')
    list_filter = ('role', 'is_staff', 'is_active')
    search_fields = ('username', 'email', 'first_name', 'last_name')
    ordering = ('username',)
    # Menambahkan field 'role' ke fieldsets edit user
    fieldsets = BaseUserAdmin.fieldsets + (
        ('Peran LMS', {'fields': ('role',)}),
    )
    add_fieldsets = BaseUserAdmin.add_fieldsets + (
        ('Peran LMS', {'fields': ('role',)}),
    )


# ==============================================================================
# CATEGORY ADMIN
# ==============================================================================

@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    """Admin konfigurasi untuk Kategori (hierarki)."""
    list_display = ('name', 'parent')
    list_filter = ('parent',)
    search_fields = ('name',)
    ordering = ('parent__name', 'name')


# ==============================================================================
# LESSON INLINE (untuk ditampilkan langsung di dalam Course admin)
# ==============================================================================

class LessonInline(admin.TabularInline):
    """Inline Lesson agar bisa ditambahkan langsung saat membuat/edit Course."""
    model = Lesson
    extra = 1
    fields = ('order', 'title', 'content', 'video_url', 'file_attachment')
    ordering = ('order',)


# ==============================================================================
# COURSE ADMIN
# ==============================================================================

@admin.register(Course)
class CourseAdmin(admin.ModelAdmin):
    """Admin konfigurasi untuk Course (Mata Kuliah)."""
    list_display = ('name', 'instructor', 'category', 'price', 'created_at')
    list_filter = ('instructor', 'category', 'created_at')
    search_fields = ('name', 'description', 'instructor__username')
    ordering = ('-created_at',)
    inlines = [LessonInline]  # Inline untuk Lesson


# ==============================================================================
# LESSON ADMIN
# ==============================================================================

@admin.register(Lesson)
class LessonAdmin(admin.ModelAdmin):
    """Admin konfigurasi untuk Lesson (Materi)."""
    list_display = ('order', 'title', 'course')
    list_filter = ('course',)
    search_fields = ('title', 'content')
    ordering = ('course', 'order')


# ==============================================================================
# ENROLLMENT ADMIN
# ==============================================================================

@admin.register(Enrollment)
class EnrollmentAdmin(admin.ModelAdmin):
    """Admin konfigurasi untuk Enrollment (Pendaftaran)."""
    list_display = ('student', 'course', 'date_enrolled')
    list_filter = ('course', 'date_enrolled')
    search_fields = ('student__username', 'course__name')
    ordering = ('-date_enrolled',)


# ==============================================================================
# PROGRESS ADMIN
# ==============================================================================

@admin.register(Progress)
class ProgressAdmin(admin.ModelAdmin):
    """Admin konfigurasi untuk Progress (Tracking Penyelesaian Materi)."""
    list_display = ('enrollment', 'lesson', 'is_completed', 'completed_at')
    list_filter = ('is_completed', 'lesson__course')
    search_fields = ('enrollment__student__username', 'lesson__title')


# ==============================================================================
# COURSE CONTENT INLINE (dari modul - konten per course)
# ==============================================================================

class CourseContentInline(admin.TabularInline):
    """Inline CourseContent agar bisa ditambahkan langsung saat membuat Course."""
    model = CourseContent
    extra = 1
    fk_name = 'course_id'  # Eksplisit karena ada dua ForeignKey di CourseContent


# ==============================================================================
# COURSE MEMBER ADMIN
# ==============================================================================

@admin.register(CourseMember)
class CourseMemberAdmin(admin.ModelAdmin):
    """Admin konfigurasi untuk CourseMember (Anggota Kelas)."""
    list_display = ('user_id', 'course_id', 'roles')
    list_filter = ('roles', 'course_id')
    search_fields = ('user_id__username', 'course_id__name')


# ==============================================================================
# COURSE CONTENT ADMIN
# ==============================================================================

@admin.register(CourseContent)
class CourseContentAdmin(admin.ModelAdmin):
    """Admin konfigurasi untuk CourseContent (Konten Kelas)."""
    list_display = ('name', 'course_id', 'parent_id')
    list_filter = ('course_id',)
    search_fields = ('name', 'description')


# ==============================================================================
# COMMENT ADMIN
# ==============================================================================

@admin.register(Comment)
class CommentAdmin(admin.ModelAdmin):
    """Admin konfigurasi untuk Comment (Komentar)."""
    list_display = ('content_id', 'member_id', 'comment')
    list_filter = ('content_id',)
    search_fields = ('comment', 'member_id__user_id__username')