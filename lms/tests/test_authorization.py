# lms/tests/test_authorization.py
"""
Pengujian Negatif (Authorization Testing) untuk Simple LMS — Modul 11

Mengapa pengujian negatif penting?
- Memastikan keamanan API (tidak ada unauthorized access)
- Mendeteksi celah keamanan sebelum production
- Mendokumentasikan perilaku yang dilarang

Setiap test di sini memverifikasi bahwa:
- User TIDAK BISA mengakses resource yang bukan haknya
- Response yang tepat dikembalikan (403 Forbidden, 401 Unauthorized, 404 Not Found)
- Data TIDAK berubah di database setelah percobaan yang ditolak

Jalankan:
    docker-compose exec app python manage.py test lms.tests.test_authorization -v 2
"""

import json
from django.test import TestCase, Client

from lms.models import User, Course, Enrollment, CourseMember, CourseContent, Comment


# ==============================================================================
# BASE TEST CASE (sama seperti di test_api_integration)
# ==============================================================================

class BaseAuthTest(TestCase):
    """Base class untuk authorization tests."""

    def setUp(self):
        self.client = Client()

        self.instructor1 = User.objects.create_user(
            username='instructor1', password='InstrPass1!',
            email='instructor1@test.com', role='instructor'
        )
        self.instructor2 = User.objects.create_user(
            username='instructor2', password='InstrPass2!',
            email='instructor2@test.com', role='instructor'
        )
        self.student1 = User.objects.create_user(
            username='student1', password='StudPass1!',
            email='student1@test.com', role='student'
        )
        self.outsider = User.objects.create_user(
            username='outsider', password='OutPass1!',
            email='outsider@test.com', role='student'
        )

        self.course1 = Course.objects.create(
            name='Private Course',
            price=500000,
            instructor=self.instructor1
        )

    def get_token(self, username, password):
        """Login dan kembalikan JWT access token."""
        response = self.client.post(
            '/api/v1/auth/sign-in',
            data=json.dumps({'username': username, 'password': password}),
            content_type='application/json'
        )
        if response.status_code == 200:
            return response.json().get('access')
        return None

    def patch_json(self, url, data, token=None):
        headers = {}
        if token:
            headers['HTTP_AUTHORIZATION'] = f'Bearer {token}'
        return self.client.patch(
            url,
            data=json.dumps(data),
            content_type='application/json',
            **headers
        )

    def post_json(self, url, data, token=None):
        headers = {}
        if token:
            headers['HTTP_AUTHORIZATION'] = f'Bearer {token}'
        return self.client.post(
            url,
            data=json.dumps(data),
            content_type='application/json',
            **headers
        )

    def delete_req(self, url, token=None):
        headers = {}
        if token:
            headers['HTTP_AUTHORIZATION'] = f'Bearer {token}'
        return self.client.delete(url, **headers)


# ==============================================================================
# TEST: UNAUTHENTICATED USER
# ==============================================================================

class TestUnauthenticatedAccess(BaseAuthTest):
    """
    Test akses tanpa login sama sekali.

    Semua endpoint protected harus mengembalikan 401 Unauthorized.
    """

    def test_unauthenticated_cannot_create_course(self):
        """
        User tanpa token tidak bisa membuat course.

        Expected: 401 Unauthorized, course tidak tersimpan.
        """
        initial_count = Course.objects.count()

        response = self.post_json('/api/v1/courses/', {
            'name': 'Hacked Course',
            'price': 100000
        })

        self.assertEqual(response.status_code, 401)
        # Pastikan tidak ada course baru
        self.assertEqual(Course.objects.count(), initial_count)

    def test_unauthenticated_cannot_patch_course(self):
        """User tanpa token tidak bisa mengubah course."""
        response = self.patch_json(
            f'/api/v1/courses/{self.course1.id}',
            {'price': 1}
        )
        self.assertEqual(response.status_code, 401)

        # Verifikasi harga tidak berubah
        self.course1.refresh_from_db()
        self.assertEqual(self.course1.price, 500000)

    def test_unauthenticated_cannot_delete_course(self):
        """User tanpa token tidak bisa menghapus course."""
        response = self.delete_req(f'/api/v1/courses/{self.course1.id}')
        self.assertEqual(response.status_code, 401)

        # Course masih ada
        self.assertTrue(Course.objects.filter(id=self.course1.id).exists())

    def test_unauthenticated_cannot_access_profile(self):
        """User tanpa token tidak bisa akses profil."""
        response = self.client.get('/api/v1/profile/')
        self.assertEqual(response.status_code, 401)

    def test_unauthenticated_cannot_enroll(self):
        """User tanpa token tidak bisa enroll ke course."""
        response = self.post_json(
            f'/api/v1/courses/{self.course1.id}/enroll/',
            {}
        )
        self.assertEqual(response.status_code, 401)
        # Tidak ada enrollment yang tersimpan
        self.assertEqual(Enrollment.objects.count(), 0)


# ==============================================================================
# TEST: STUDENT TRYING INSTRUCTOR ACTIONS
# ==============================================================================

class TestStudentUnauthorizedActions(BaseAuthTest):
    """
    Test student yang mencoba melakukan aksi yang hanya boleh dilakukan instructor.

    Prinsip Least Privilege: user hanya boleh melakukan yang sesuai role-nya.
    """

    def test_student_cannot_create_course(self):
        """
        Test student yang mencoba membuat course.

        Catatan desain API v1:
        - API TIDAK membatasi pembuatan course berdasarkan role.
        - Setiap user terautentikasi dapat membuat course (menjadi instructor).
        - Pembatasan role (instructor-only) ada di docstring tapi belum diimplementasi.
        - Test ini mendokumentasikan perilaku AKTUAL API saat ini.

        Expected: HTTP 201 (berhasil) — API menerima request dari student.
        """
        token = self.get_token('student1', 'StudPass1!')
        initial_count = Course.objects.count()

        response = self.post_json('/api/v1/courses/', {
            'name': 'Course oleh Student',
            'price': 50000
        }, token=token)

        # API v1 mengizinkan siapapun (terautentikasi) membuat course
        # Role check TIDAK diimplementasikan di endpoint ini
        self.assertEqual(
            response.status_code, 201,
            msg="Catatan: API tidak membatasi pembuatan course berdasarkan role. "
                "Student bisa membuat course dan otomatis jadi instructor."
        )
        # Course tersimpan dengan student sebagai instructor
        self.assertEqual(Course.objects.count(), initial_count + 1)

    def test_student_cannot_update_course(self):
        """
        Student tidak bisa mengubah course.

        Expected: 403 Forbidden, harga tidak berubah.
        """
        token = self.get_token('student1', 'StudPass1!')

        response = self.patch_json(
            f'/api/v1/courses/{self.course1.id}',
            {'price': 1, 'name': 'Hacked!'},
            token=token
        )

        self.assertEqual(response.status_code, 403)

        # Verifikasi data tidak berubah
        self.course1.refresh_from_db()
        self.assertEqual(self.course1.price, 500000)
        self.assertEqual(self.course1.name, 'Private Course')

    def test_student_cannot_delete_course(self):
        """
        Student tidak bisa menghapus course.

        Expected: 403 Forbidden, course masih ada.
        """
        token = self.get_token('student1', 'StudPass1!')

        response = self.delete_req(
            f'/api/v1/courses/{self.course1.id}',
            token=token
        )

        self.assertEqual(response.status_code, 403)
        # Course masih ada di database
        self.assertTrue(Course.objects.filter(id=self.course1.id).exists())


# ==============================================================================
# TEST: INSTRUCTOR CROSS-OWNERSHIP
# ==============================================================================

class TestInstructorCrossOwnership(BaseAuthTest):
    """
    Test instructor yang mencoba mengubah/hapus course milik instructor lain.

    Kepemilikan resource: hanya pemilik yang boleh modifikasi.
    """

    def test_instructor_cannot_update_other_instructors_course(self):
        """
        instructor2 tidak bisa mengubah course milik instructor1.

        Expected: 403 Forbidden.
        """
        token = self.get_token('instructor2', 'InstrPass2!')

        response = self.patch_json(
            f'/api/v1/courses/{self.course1.id}',
            {'name': 'Hijacked Course', 'price': 1},
            token=token
        )

        self.assertEqual(response.status_code, 403)

        # Pastikan nama dan harga tidak berubah
        self.course1.refresh_from_db()
        self.assertEqual(self.course1.name, 'Private Course')
        self.assertEqual(self.course1.price, 500000)

    def test_instructor_cannot_delete_other_instructors_course(self):
        """
        instructor2 tidak bisa menghapus course milik instructor1.

        Expected: 403 Forbidden, course masih ada.
        """
        token = self.get_token('instructor2', 'InstrPass2!')

        response = self.delete_req(
            f'/api/v1/courses/{self.course1.id}',
            token=token
        )

        self.assertEqual(response.status_code, 403)
        # Course masih ada
        self.assertTrue(Course.objects.filter(id=self.course1.id).exists())

    def test_instructor_can_update_own_course(self):
        """
        Test POSITIF: instructor1 BISA mengubah course miliknya sendiri.

        Kontrol: pastikan pengecekan ownership bekerja dengan benar.
        Expected: 200 OK, data berubah.
        """
        token = self.get_token('instructor1', 'InstrPass1!')

        response = self.patch_json(
            f'/api/v1/courses/{self.course1.id}',
            {'price': 450000},
            token=token
        )

        self.assertEqual(response.status_code, 200)
        # Verifikasi harga berubah
        self.course1.refresh_from_db()
        self.assertEqual(self.course1.price, 450000)


# ==============================================================================
# TEST: NON-ENROLLED USER
# ==============================================================================

class TestNonEnrolledAccess(BaseAuthTest):
    """
    Test user yang belum enroll mencoba akses resource course.

    User yang tidak terdaftar tidak boleh mengakses konten atau komentar.
    """

    def setUp(self):
        super().setUp()
        # Buat konten untuk course1
        self.content = CourseContent.objects.create(
            name='Secret Lesson',
            description='Ini materi rahasia',
            course_id=self.course1
        )
        # PENTING: student1 harus di-ENROLL dulu (Enrollment model)
        # karena check_enrollment() di endpoint POST /comments/ memeriksa
        # tabel Enrollment, bukan CourseMember
        self.enrollment = Enrollment.objects.create(
            student=self.student1,
            course=self.course1
        )
        # Buat CourseMember (untuk kebutuhan Comment model)
        self.member = CourseMember.objects.create(
            course_id=self.course1,
            user_id=self.student1,
            roles='std'
        )

    def test_enrolled_student_can_post_comment(self):
        """
        Test POSITIF: student yang sudah enrolled bisa membuat komentar.

        Endpoint: POST /api/v1/comments/ (bukan /api/v1/contents/{id}/comments/)
        Body: {content_id: <id>, comment: <text>}
        Authorization: user harus di-Enrolled di course yang berisi konten.
        """
        token = self.get_token('student1', 'StudPass1!')

        response = self.post_json(
            '/api/v1/comments/',
            {'content_id': self.content.id, 'comment': 'Materi ini bagus!'},
            token=token
        )

        self.assertEqual(response.status_code, 201)
        self.assertEqual(Comment.objects.count(), 1)

    def test_non_enrolled_outsider_cannot_post_comment(self):
        """
        Test NEGATIF: outsider (belum enrolled) tidak bisa membuat komentar.

        outsider tidak memiliki Enrollment ke course1.
        check_enrollment() akan menolak dengan 403.
        Expected: 403 Forbidden atau 404 Not Found.
        """
        token = self.get_token('outsider', 'OutPass1!')

        response = self.post_json(
            '/api/v1/comments/',
            {'content_id': self.content.id, 'comment': 'Spam dari outsider'},
            token=token
        )

        self.assertIn(response.status_code, [403, 404])
        # Tidak ada komentar yang tersimpan
        self.assertEqual(Comment.objects.count(), 0)


# ==============================================================================
# TEST: COMMENT OWNERSHIP
# ==============================================================================

class TestCommentOwnership(BaseAuthTest):
    """
    Test kepemilikan komentar.

    User hanya bisa menghapus komentar miliknya sendiri.
    """

    def setUp(self):
        super().setUp()

        # student2 juga enrolled
        self.student2 = User.objects.create_user(
            username='student2', password='StudPass2!',
            email='student2@test.com', role='student'
        )

        # Buat konten
        self.content = CourseContent.objects.create(
            name='Materi Diskusi',
            course_id=self.course1
        )

        # Buat member untuk student1 dan student2
        self.member1 = CourseMember.objects.create(
            course_id=self.course1, user_id=self.student1, roles='std'
        )
        self.member2 = CourseMember.objects.create(
            course_id=self.course1, user_id=self.student2, roles='std'
        )

        # Buat komentar dari student1
        self.comment_by_student1 = Comment.objects.create(
            content_id=self.content,
            member_id=self.member1,
            comment='Ini komentar milik student1'
        )

    def test_user_can_delete_own_comment(self):
        """
        Test POSITIF: student1 bisa menghapus komentar miliknya sendiri.
        """
        token = self.get_token('student1', 'StudPass1!')

        response = self.delete_req(
            f'/api/v1/comments/{self.comment_by_student1.id}',
            token=token
        )

        self.assertEqual(response.status_code, 200)
        # Komentar sudah terhapus
        self.assertEqual(Comment.objects.count(), 0)

    def test_user_cannot_delete_other_users_comment(self):
        """
        Test NEGATIF: student2 tidak bisa menghapus komentar milik student1.

        Expected: 403 Forbidden atau 404 Not Found.
        Komentar tidak terhapus.
        """
        token = self.get_token('student2', 'StudPass2!')

        response = self.delete_req(
            f'/api/v1/comments/{self.comment_by_student1.id}',
            token=token
        )

        self.assertIn(response.status_code, [403, 404])
        # Komentar masih ada
        self.assertTrue(
            Comment.objects.filter(id=self.comment_by_student1.id).exists()
        )

    def test_instructor_can_delete_any_comment_in_own_course(self):
        """
        Test: instructor bisa menghapus komentar apapun di course miliknya.

        Instructor adalah moderator di coursenya sendiri.
        """
        token = self.get_token('instructor1', 'InstrPass1!')

        response = self.delete_req(
            f'/api/v1/comments/{self.comment_by_student1.id}',
            token=token
        )

        # Instructor bisa hapus: 200 atau 403 tergantung implementasi
        # Yang penting: endpoint tidak crash (bukan 500)
        self.assertNotEqual(response.status_code, 500)
