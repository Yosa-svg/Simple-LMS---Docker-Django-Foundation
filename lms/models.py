from django.db import models
from django.contrib.auth.models import AbstractUser


# ==============================================================================
# CUSTOM USER MODEL (dengan role: admin, instructor, student)
# ==============================================================================

class User(AbstractUser):
    """
    Custom User model yang meng-extend AbstractUser bawaan Django.
    Menambahkan field 'role' untuk membedakan admin, instructor, dan student.
    """
    ROLE_CHOICES = [
        ('admin', 'Admin'),
        ('instructor', 'Instructor'),
        ('student', 'Student'),
    ]
    role = models.CharField(
        'peran',
        max_length=20,
        choices=ROLE_CHOICES,
        default='student'
    )

    def __str__(self):
        return f"{self.username} ({self.get_role_display()})"

    class Meta:
        verbose_name = 'Pengguna'
        verbose_name_plural = 'Pengguna'


# ==============================================================================
# CATEGORY MODEL (self-referencing untuk hierarchy)
# ==============================================================================

class Category(models.Model):
    """
    Model kategori yang mendukung hierarki (kategori dapat memiliki sub-kategori).
    Menggunakan self-referencing ForeignKey dengan related_name='subcategories'.
    """
    name = models.CharField('nama kategori', max_length=100)
    parent = models.ForeignKey(
        'self',
        verbose_name='induk kategori',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='subcategories'
    )

    def __str__(self):
        if self.parent:
            return f"{self.parent.name} > {self.name}"
        return self.name

    class Meta:
        verbose_name = 'Kategori'
        verbose_name_plural = 'Kategori'


# ==============================================================================
# CUSTOM MANAGERS (Optimasi Query - Rubrik Tugas)
# ==============================================================================

class CourseQuerySet(models.QuerySet):
    """Custom QuerySet untuk Course dengan optimasi query."""

    def for_listing(self):
        """
        Optimized untuk halaman list course.
        Menggunakan select_related untuk mencegah N+1 Problem saat
        mengakses data instructor (User) dan category.
        Equivalent SQL: SELECT ... FROM course
                        JOIN auth_user ON course.instructor_id = auth_user.id
                        JOIN category ON course.category_id = category.id
        """
        return self.select_related('instructor', 'category')


class CourseManager(models.Manager):
    """Custom Manager untuk Course model."""

    def get_queryset(self):
        return CourseQuerySet(self.model, using=self._db)

    def for_listing(self):
        """QuerySet yang dioptimasi untuk halaman list (mencegah N+1 Problem)."""
        return self.get_queryset().for_listing()


class EnrollmentQuerySet(models.QuerySet):
    """Custom QuerySet untuk Enrollment dengan optimasi query."""

    def for_student_dashboard(self, student):
        """
        Optimized untuk student dashboard.
        Menggunakan select_related untuk mencegah N+1 Problem saat mengakses
        detail course, instructor course, dan category.
        Menggunakan prefetch_related untuk mengambil semua progress sekaligus.
        """
        return (
            self.filter(student=student)
            .select_related(
                'course',
                'course__instructor',
                'course__category',
            )
            .prefetch_related('progress_set', 'progress_set__lesson')
        )


class EnrollmentManager(models.Manager):
    """Custom Manager untuk Enrollment model."""

    def get_queryset(self):
        return EnrollmentQuerySet(self.model, using=self._db)

    def for_student_dashboard(self, student):
        """QuerySet yang dioptimasi untuk student dashboard."""
        return self.get_queryset().for_student_dashboard(student)


# ==============================================================================
# COURSE MODEL (dengan instructor dan category)
# ==============================================================================

class Course(models.Model):
    """
    Model untuk mata kuliah / kursus.
    Berelasi dengan User (sebagai instructor) dan Category.
    """
    name = models.CharField('nama matkul', max_length=100)
    description = models.TextField('deskripsi', default='-')
    price = models.IntegerField('harga', default=10000)
    image = models.ImageField('gambar', upload_to='course_images/', null=True, blank=True)
    instructor = models.ForeignKey(
        User,
        verbose_name='pengajar',
        on_delete=models.RESTRICT,
        related_name='courses_taught',
        limit_choices_to={'role': 'instructor'},
    )
    category = models.ForeignKey(
        Category,
        verbose_name='kategori',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='courses'
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    # Mengaktifkan Custom Manager
    objects = CourseManager()

    def __str__(self):
        return self.name

    class Meta:
        verbose_name = 'Mata Kuliah'
        verbose_name_plural = 'Mata Kuliah'
        ordering = ['-created_at']
        indexes = [
            # Index pada price — sering dipakai filter() dan order_by() di lab
            models.Index(fields=['price'], name='idx_course_price'),
            # Index pada name — dipakai pencarian/contains
            models.Index(fields=['name'], name='idx_course_name'),
            # Composite index instructor + price — untuk query dashboard dosen
            models.Index(fields=['instructor', 'price'], name='idx_course_instructor_price'),
            # Index descending created_at — untuk default ordering
            models.Index(fields=['-created_at'], name='idx_course_created_desc'),
        ]


# ==============================================================================
# LESSON MODEL (dengan ordering)
# ==============================================================================

class Lesson(models.Model):
    """
    Model untuk materi/konten pelajaran dalam sebuah course.
    Memiliki field 'order' untuk menentukan urutan tampil.
    """
    title = models.CharField('judul materi', max_length=200)
    content = models.TextField('isi materi')
    video_url = models.CharField(
        'URL Video',
        max_length=200,
        null=True,
        blank=True
    )
    file_attachment = models.FileField(
        'File Lampiran',
        upload_to='lesson_files/',
        null=True,
        blank=True
    )
    order = models.PositiveIntegerField('urutan', default=0)
    course = models.ForeignKey(
        Course,
        verbose_name='matkul',
        on_delete=models.CASCADE,
        related_name='lessons'
    )

    def __str__(self):
        return f"[{self.order}] {self.title} - {self.course.name}"

    class Meta:
        verbose_name = 'Materi'
        verbose_name_plural = 'Materi'
        ordering = ['order']  # Selalu diurutkan berdasarkan field 'order'


# ==============================================================================
# ENROLLMENT MODEL (dengan unique constraint)
# ==============================================================================

class Enrollment(models.Model):
    """
    Model untuk pendaftaran student ke course.
    Memiliki UniqueConstraint agar satu student hanya bisa daftar sekali
    per course (mencegah duplikasi).
    """
    student = models.ForeignKey(
        User,
        verbose_name='siswa',
        on_delete=models.CASCADE,
        related_name='enrollments',
        limit_choices_to={'role': 'student'},
    )
    course = models.ForeignKey(
        Course,
        verbose_name='matkul',
        on_delete=models.CASCADE,
        related_name='enrollments'
    )
    date_enrolled = models.DateTimeField('tanggal daftar', auto_now_add=True)

    # Mengaktifkan Custom Manager
    objects = EnrollmentManager()

    def __str__(self):
        return f"{self.student.username} -> {self.course.name}"

    class Meta:
        verbose_name = 'Pendaftaran'
        verbose_name_plural = 'Pendaftaran'
        constraints = [
            models.UniqueConstraint(
                fields=['student', 'course'],
                name='unique_student_course_enrollment'
            )
        ]


# ==============================================================================
# PROGRESS MODEL (tracking lesson completion)
# ==============================================================================

class Progress(models.Model):
    """
    Model untuk melacak progress siswa per materi (lesson).
    Setiap enrollment + lesson adalah kombinasi unik.
    """
    enrollment = models.ForeignKey(
        Enrollment,
        verbose_name='pendaftaran',
        on_delete=models.CASCADE,
        related_name='progress_set'
    )
    lesson = models.ForeignKey(
        Lesson,
        verbose_name='materi',
        on_delete=models.CASCADE,
        related_name='progress_set'
    )
    is_completed = models.BooleanField('selesai', default=False)
    completed_at = models.DateTimeField('waktu selesai', null=True, blank=True)

    def __str__(self):
        status = '✓' if self.is_completed else '○'
        return f"{status} {self.enrollment.student.username} - {self.lesson.title}"

    class Meta:
        verbose_name = 'Progress'
        verbose_name_plural = 'Progress'
        constraints = [
            models.UniqueConstraint(
                fields=['enrollment', 'lesson'],
                name='unique_progress_per_lesson'
            )
        ]


# ==============================================================================
# COURSE MEMBER MODEL (anggota kelas - dari modul)
# ==============================================================================

ROLE_OPTIONS = [
    ('std', 'Siswa'),
    ('ast', 'Asisten'),
]


class CourseMember(models.Model):
    """
    Model untuk anggota kelas.
    Menghubungkan User dengan Course dengan role tertentu (siswa/asisten).
    Digunakan untuk mengelola partisipasi di dalam kelas.
    """
    course_id = models.ForeignKey(
        Course,
        verbose_name='matkul',
        on_delete=models.RESTRICT
    )
    user_id = models.ForeignKey(
        User,
        verbose_name='pengguna',
        on_delete=models.RESTRICT
    )
    roles = models.CharField(
        'peran',
        max_length=3,
        choices=ROLE_OPTIONS,
        default='std'
    )

    def __str__(self):
        return f"{self.user_id} - {self.course_id} ({self.get_roles_display()})"

    class Meta:
        verbose_name = 'Anggota Kelas'
        verbose_name_plural = 'Anggota Kelas'


# ==============================================================================
# COURSE CONTENT MODEL (konten kelas - dari modul)
# ==============================================================================

class CourseContent(models.Model):
    """
    Model untuk konten/materi kelas yang mendukung hierarki.
    Menggunakan self-referencing ForeignKey untuk parent-child (modul/sub-modul).
    """
    name = models.CharField('judul konten', max_length=200)
    description = models.TextField('deskripsi', default='-')
    video_url = models.CharField(
        'URL Video',
        max_length=200,
        null=True,
        blank=True
    )
    file_attachment = models.FileField(
        'File',
        upload_to='content_files/',
        null=True,
        blank=True
    )
    course_id = models.ForeignKey(
        Course,
        verbose_name='matkul',
        on_delete=models.RESTRICT
    )
    parent_id = models.ForeignKey(
        'self',
        verbose_name='induk',
        on_delete=models.RESTRICT,
        null=True,
        blank=True
    )

    def __str__(self):
        return self.name

    class Meta:
        verbose_name = 'Konten Kelas'
        verbose_name_plural = 'Konten Kelas'


# ==============================================================================
# COMMENT MODEL (komentar pada konten - dari modul)
# ==============================================================================

class Comment(models.Model):
    """
    Model untuk komentar pada konten kelas.
    Terhubung ke CourseContent dan CourseMember.
    """
    content_id = models.ForeignKey(
        CourseContent,
        verbose_name='konten',
        on_delete=models.CASCADE
    )
    member_id = models.ForeignKey(
        CourseMember,
        verbose_name='pengguna',
        on_delete=models.CASCADE
    )
    comment = models.TextField('komentar')

    def __str__(self):
        return f"Komentar oleh {self.member_id.user_id} pada {self.content_id}"

    class Meta:
        verbose_name = 'Komentar'
        verbose_name_plural = 'Komentar'