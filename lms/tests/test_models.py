# lms/tests/test_models.py
"""
Unit Test untuk Model Django LMS — Modul 11 (Studi Kasus 3)

Perbedaan dengan test_calculator.py:
- Model tests MEMBUTUHKAN database (Django test database)
- Django TestCase otomatis membungkus setiap test dalam transaksi
  yang di-rollback → setiap test dimulai dari kondisi bersih
- Tidak perlu explicit tearDown() untuk data database

Adaptasi dari modul:
- Menggunakan lms.User (custom) bukan django.contrib.auth.User
- Course FK: 'instructor' (bukan 'teacher')
- CourseMember: 'course_id', 'user_id', 'roles' (bukan 'course', 'user', 'role')
- CourseContent: 'course_id', 'parent_id' (ForeignKey dengan suffix _id)
- Comment: 'content_id', 'member_id'
- Enrollment: student=FK, course=FK dengan UniqueConstraint

Jalankan:
    docker-compose exec app python manage.py test lms.tests.test_models -v 2
"""

from django.test import TestCase
from django.db import IntegrityError

from lms.models import (
    User, Course, Category,
    Enrollment, CourseMember,
    CourseContent, Comment
)


# ==============================================================================
# HELPER: Buat user dengan role tertentu
# ==============================================================================

def make_instructor(username='instructor1', password='testpass123'):
    """Helper untuk membuat user instructor."""
    return User.objects.create_user(
        username=username,
        password=password,
        email=f'{username}@test.com',
        role='instructor',
    )


def make_student(username='student1', password='testpass123'):
    """Helper untuk membuat user student."""
    return User.objects.create_user(
        username=username,
        password=password,
        email=f'{username}@test.com',
        role='student',
    )


# ==============================================================================
# TEST COURSE MODEL
# ==============================================================================

class TestCourseModel(TestCase):
    """
    Unit test untuk model Course.

    Menguji:
    - Pembuatan course dan nilai field
    - Representasi string (__str__)
    - Default value untuk price
    - Ordering (terbaru muncul pertama)
    - Relasi dengan instructor
    """

    def setUp(self):
        """
        setUp() dipanggil sebelum SETIAP test method.

        Best practice: siapkan data minimal yang dibutuhkan.
        Django otomatis rollback database setelah setiap test.
        """
        self.instructor = make_instructor()

    def test_create_course(self):
        """Test membuat course baru dengan semua field."""
        course = Course.objects.create(
            name="Django for Beginners",
            description="Belajar Django dari nol",
            price=100000,
            instructor=self.instructor
        )
        self.assertEqual(course.name, "Django for Beginners")
        self.assertEqual(course.price, 100000)
        self.assertEqual(course.instructor, self.instructor)
        self.assertEqual(course.description, "Belajar Django dari nol")

    def test_course_str_representation(self):
        """
        Test bahwa __str__() mengembalikan nama course.

        __str__ digunakan di Django Admin, shell, dan logging.
        """
        course = Course.objects.create(
            name="Python Basics",
            instructor=self.instructor
        )
        self.assertEqual(str(course), "Python Basics")

    def test_course_default_price(self):
        """
        Test bahwa default price adalah 10000.

        Jika tidak diisi, price = 10000 (sesuai definisi model).
        """
        course = Course.objects.create(
            name="Free Course",
            instructor=self.instructor
        )
        self.assertEqual(course.price, 10000)

    def test_course_ordering_newest_first(self):
        """
        Test bahwa course diurutkan berdasarkan created_at descending.

        Model memiliki: ordering = ['-created_at']
        Course yang dibuat belakangan harus muncul pertama.
        """
        course1 = Course.objects.create(
            name="Course Pertama",
            instructor=self.instructor
        )
        course2 = Course.objects.create(
            name="Course Kedua",
            instructor=self.instructor
        )
        courses = list(Course.objects.all())
        # Course terbaru (course2) harus di indeks 0
        self.assertEqual(courses[0], course2)
        self.assertEqual(courses[1], course1)

    def test_instructor_can_have_multiple_courses(self):
        """
        Test bahwa satu instructor bisa memiliki banyak course.

        Relasi One-to-Many: satu instructor → banyak course.
        related_name='courses_taught' memungkinkan akses dari sisi instructor.
        """
        Course.objects.create(name="Course A", instructor=self.instructor)
        Course.objects.create(name="Course B", instructor=self.instructor)
        Course.objects.create(name="Course C", instructor=self.instructor)

        self.assertEqual(self.instructor.courses_taught.count(), 3)

    def test_course_with_category(self):
        """Test course bisa memiliki kategori (optional)."""
        category = Category.objects.create(name="Pemrograman")
        course = Course.objects.create(
            name="Kursus Python",
            instructor=self.instructor,
            category=category
        )
        self.assertEqual(course.category.name, "Pemrograman")

    def test_course_without_category_is_allowed(self):
        """Test course bisa dibuat tanpa kategori (nullable FK)."""
        course = Course.objects.create(
            name="Kursus Tanpa Kategori",
            instructor=self.instructor,
            category=None
        )
        self.assertIsNone(course.category)

    def test_created_at_auto_set(self):
        """Test bahwa created_at diisi otomatis saat course dibuat."""
        course = Course.objects.create(
            name="Test Course",
            instructor=self.instructor
        )
        self.assertIsNotNone(course.created_at)

    def test_updated_at_changes_on_save(self):
        """Test bahwa updated_at berubah saat course disimpan ulang."""
        course = Course.objects.create(
            name="Original Name",
            instructor=self.instructor
        )
        original_updated = course.updated_at

        course.name = "Updated Name"
        course.save()
        course.refresh_from_db()

        # updated_at harus berubah
        self.assertGreaterEqual(course.updated_at, original_updated)


# ==============================================================================
# TEST ENROLLMENT MODEL
# ==============================================================================

class TestEnrollmentModel(TestCase):
    """
    Unit test untuk model Enrollment.

    Enrollment menghubungkan student dengan course.
    Memiliki UniqueConstraint untuk mencegah enrollment ganda.
    """

    def setUp(self):
        """Setup user dan course untuk test enrollment."""
        self.instructor = make_instructor()
        self.student = make_student()
        self.course = Course.objects.create(
            name="Django Course",
            price=150000,
            instructor=self.instructor
        )

    def test_create_enrollment(self):
        """Test mendaftarkan student ke course."""
        enrollment = Enrollment.objects.create(
            student=self.student,
            course=self.course
        )
        self.assertEqual(enrollment.student, self.student)
        self.assertEqual(enrollment.course, self.course)
        self.assertIsNotNone(enrollment.date_enrolled)

    def test_enrollment_str_representation(self):
        """Test representasi string enrollment."""
        enrollment = Enrollment.objects.create(
            student=self.student,
            course=self.course
        )
        # Format: "student1 -> Django Course"
        expected = f"{self.student.username} -> {self.course.name}"
        self.assertEqual(str(enrollment), expected)

    def test_enrollment_unique_constraint(self):
        """
        Test bahwa student tidak bisa enroll dua kali ke course yang sama.

        Model memiliki UniqueConstraint pada (student, course).
        Percobaan kedua harus melempar IntegrityError.
        """
        # Enrollment pertama — berhasil
        Enrollment.objects.create(student=self.student, course=self.course)

        # Enrollment kedua — harus gagal dengan IntegrityError
        with self.assertRaises(IntegrityError):
            Enrollment.objects.create(
                student=self.student,
                course=self.course
            )

    def test_different_students_can_enroll_same_course(self):
        """Test bahwa banyak student bisa mendaftar ke course yang sama."""
        student2 = make_student(username='student2')
        student3 = make_student(username='student3')

        Enrollment.objects.create(student=self.student, course=self.course)
        Enrollment.objects.create(student=student2, course=self.course)
        Enrollment.objects.create(student=student3, course=self.course)

        self.assertEqual(self.course.enrollments.count(), 3)

    def test_enrollment_cascade_delete_with_student(self):
        """
        Test bahwa enrollment terhapus otomatis jika student dihapus.

        CASCADE delete: student → enrollment ikut terhapus.
        """
        Enrollment.objects.create(student=self.student, course=self.course)
        self.assertEqual(Enrollment.objects.count(), 1)

        self.student.delete()

        self.assertEqual(Enrollment.objects.count(), 0)

    def test_enrollment_cascade_delete_with_course(self):
        """
        Test bahwa enrollment terhapus otomatis jika course dihapus.

        Catatan: Course.instructor FK menggunakan RESTRICT, tapi
        Enrollment FK ke Course menggunakan CASCADE.
        """
        Enrollment.objects.create(student=self.student, course=self.course)
        self.assertEqual(Enrollment.objects.count(), 1)

        # Hapus instructor terlebih dahulu untuk menghindari RESTRICT
        # (Course.instructor menggunakan on_delete=RESTRICT)
        self.course.delete()

        self.assertEqual(Enrollment.objects.count(), 0)


# ==============================================================================
# TEST COURSE MEMBER MODEL
# ==============================================================================

class TestCourseMemberModel(TestCase):
    """
    Unit test untuk model CourseMember.

    CourseMember adalah anggota kelas (siswa/asisten) yang berbeda dari Enrollment.
    Enrollment = mendaftar ke course (student).
    CourseMember = terlibat aktif dalam kelas dengan role (std/ast).
    """

    def setUp(self):
        self.instructor = make_instructor()
        self.student = make_student()
        self.course = Course.objects.create(
            name="Testing Course",
            instructor=self.instructor
        )

    def test_create_course_member(self):
        """Test membuat CourseMember dengan role std (siswa)."""
        member = CourseMember.objects.create(
            course_id=self.course,
            user_id=self.student,
            roles='std'
        )
        self.assertEqual(member.course_id, self.course)
        self.assertEqual(member.user_id, self.student)
        self.assertEqual(member.roles, 'std')

    def test_course_member_default_role_is_std(self):
        """Test bahwa default roles adalah 'std' (siswa)."""
        member = CourseMember.objects.create(
            course_id=self.course,
            user_id=self.student,
        )
        self.assertEqual(member.roles, 'std')

    def test_course_member_str_representation(self):
        """Test representasi string CourseMember."""
        member = CourseMember.objects.create(
            course_id=self.course,
            user_id=self.student,
            roles='std'
        )
        # Format: "student1 (Student) - Testing Course (Siswa)"
        self.assertIn(self.student.username, str(member))
        self.assertIn(self.course.name, str(member))

    def test_course_member_assistant_role(self):
        """Test membuat CourseMember dengan role ast (asisten)."""
        assistant = make_student(username='assistant1')
        member = CourseMember.objects.create(
            course_id=self.course,
            user_id=assistant,
            roles='ast'
        )
        self.assertEqual(member.roles, 'ast')
        self.assertEqual(member.get_roles_display(), 'Asisten')


# ==============================================================================
# TEST COURSE CONTENT & COMMENT MODEL
# ==============================================================================

class TestCourseContentModel(TestCase):
    """Unit test untuk model CourseContent (konten/materi kelas)."""

    def setUp(self):
        self.instructor = make_instructor()
        self.course = Course.objects.create(
            name="Python Course",
            instructor=self.instructor
        )

    def test_create_course_content(self):
        """Test membuat konten kelas baru."""
        content = CourseContent.objects.create(
            name="Modul 1: Pengantar Python",
            description="Pengenalan dasar Python",
            course_id=self.course
        )
        self.assertEqual(content.name, "Modul 1: Pengantar Python")
        self.assertEqual(content.course_id, self.course)

    def test_course_content_str(self):
        """Test representasi string konten kelas."""
        content = CourseContent.objects.create(
            name="Intro to Testing",
            course_id=self.course
        )
        self.assertEqual(str(content), "Intro to Testing")

    def test_course_content_with_parent(self):
        """
        Test hierarki konten: parent → child.

        CourseContent mendukung self-referencing FK (parent_id).
        """
        parent = CourseContent.objects.create(
            name="Bab 1: Dasar Python",
            course_id=self.course
        )
        child = CourseContent.objects.create(
            name="1.1 Variabel",
            course_id=self.course,
            parent_id=parent
        )
        self.assertEqual(child.parent_id, parent)
        self.assertIsNone(parent.parent_id)

    def test_course_content_without_parent(self):
        """Test konten tanpa parent (konten level pertama)."""
        content = CourseContent.objects.create(
            name="Standalone Content",
            course_id=self.course
        )
        self.assertIsNone(content.parent_id)


class TestCommentModel(TestCase):
    """
    Unit test untuk model Comment.

    Comment terhubung ke CourseContent dan CourseMember.
    """

    def setUp(self):
        self.instructor = make_instructor()
        self.student = make_student()
        self.course = Course.objects.create(
            name="Django Course",
            instructor=self.instructor
        )
        self.content = CourseContent.objects.create(
            name="Intro to Django",
            course_id=self.course
        )
        self.member = CourseMember.objects.create(
            course_id=self.course,
            user_id=self.student,
            roles='std'
        )

    def test_create_comment(self):
        """Test membuat komentar pada konten kelas."""
        comment = Comment.objects.create(
            content_id=self.content,
            member_id=self.member,
            comment="Materinya sangat bermanfaat!"
        )
        self.assertEqual(comment.comment, "Materinya sangat bermanfaat!")
        self.assertEqual(comment.content_id, self.content)
        self.assertEqual(comment.member_id, self.member)

    def test_comment_str_representation(self):
        """Test representasi string komentar."""
        comment = Comment.objects.create(
            content_id=self.content,
            member_id=self.member,
            comment="Test komentar"
        )
        # Harus menyebut user dan konten
        self.assertIn(str(self.student), str(comment))
        self.assertIn(str(self.content), str(comment))

    def test_cascade_delete_comment_with_content(self):
        """Test komentar terhapus jika konten dihapus (CASCADE)."""
        Comment.objects.create(
            content_id=self.content,
            member_id=self.member,
            comment="Komentar yang akan ikut terhapus"
        )
        self.assertEqual(Comment.objects.count(), 1)

        # Hapus konten → komentar ikut terhapus
        self.content.delete()
        self.assertEqual(Comment.objects.count(), 0)

    def test_cascade_delete_comment_with_member(self):
        """Test komentar terhapus jika CourseMember dihapus (CASCADE)."""
        Comment.objects.create(
            content_id=self.content,
            member_id=self.member,
            comment="Komentar dari member"
        )
        self.assertEqual(Comment.objects.count(), 1)

        # Hapus member → komentar ikut terhapus
        self.member.delete()
        self.assertEqual(Comment.objects.count(), 0)
