# lms/tests/test_api_integration.py
"""
Integration Test untuk API Endpoints Simple LMS — Modul 11 (Studi Kasus)

Perbedaan dengan Unit Test:
- Melibatkan HTTP request (melalui django.test.Client)
- Menggunakan database test yang nyata (bukan mock)
- Menguji interaksi antara request → middleware → view → database → response
- Lebih lambat dari unit test, tapi lebih mendekati kondisi real

Komponen yang diuji bersama:
    HTTP Request → Middleware → Ninja Router → Endpoint Function → DB → Response

Jalankan:
    docker-compose exec app python manage.py test lms.tests.test_api_integration -v 2
"""

import json
from django.test import TestCase, Client

from lms.models import User, Course, Enrollment, CourseMember, CourseContent


# ==============================================================================
# BASE TEST CASE
# ==============================================================================

class BaseLMSAPITest(TestCase):
    """
    Base class untuk integration test API.

    Menyiapkan data umum dan helper method yang digunakan di semua test class.
    Setiap test class yang inherit BaseLMSAPITest mendapat:
    - Django test Client
    - User: instructor1, instructor2, student1, student2
    - Course: course1 (milik instructor1), course2 (milik instructor2)
    """

    def setUp(self):
        self.client = Client()

        # Buat users
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
        self.student2 = User.objects.create_user(
            username='student2', password='StudPass2!',
            email='student2@test.com', role='student'
        )

        # Buat courses
        self.course1 = Course.objects.create(
            name='Kursus Django Testing',
            description='Belajar automated testing',
            price=200000,
            instructor=self.instructor1
        )
        self.course2 = Course.objects.create(
            name='Kursus Python Lanjutan',
            description='Python untuk profesional',
            price=300000,
            instructor=self.instructor2
        )

    def get_token(self, username, password):
        """
        Helper: Login dan kembalikan JWT access token.

        Digunakan untuk authenticated requests.
        """
        response = self.client.post(
            '/api/v1/auth/sign-in',
            data=json.dumps({'username': username, 'password': password}),
            content_type='application/json'
        )
        if response.status_code == 200:
            return response.json().get('access')
        return None

    def auth_header(self, token):
        """Helper: Kembalikan dict HTTP_AUTHORIZATION untuk digunakan di request."""
        return {'HTTP_AUTHORIZATION': f'Bearer {token}'}

    def post_json(self, url, data, token=None):
        """Helper: POST request dengan JSON body (opsional dengan token)."""
        headers = {}
        if token:
            headers['HTTP_AUTHORIZATION'] = f'Bearer {token}'
        return self.client.post(
            url,
            data=json.dumps(data),
            content_type='application/json',
            **headers
        )

    def patch_json(self, url, data, token=None):
        """Helper: PATCH request dengan JSON body (opsional dengan token)."""
        headers = {}
        if token:
            headers['HTTP_AUTHORIZATION'] = f'Bearer {token}'
        return self.client.patch(
            url,
            data=json.dumps(data),
            content_type='application/json',
            **headers
        )

    def delete_req(self, url, token=None):
        """Helper: DELETE request (opsional dengan token)."""
        headers = {}
        if token:
            headers['HTTP_AUTHORIZATION'] = f'Bearer {token}'
        return self.client.delete(url, **headers)


# ==============================================================================
# TEST: REGISTRASI USER
# ==============================================================================

class TestRegisterAPI(BaseLMSAPITest):
    """
    Integration test untuk endpoint POST /api/v1/register/.

    Menguji: HTTP request → schema validation → User.objects.create_user() → response
    """

    def test_register_new_user_success(self):
        """
        Test registrasi user baru dengan data valid.

        Happy path: semua field valid → HTTP 201 Created.
        """
        data = {
            'username': 'newstudent',
            'password': 'TestPass123!',
            'email': 'newstudent@test.com',
            'first_name': 'New',
            'last_name': 'Student',
            'role': 'student'
        }
        response = self.post_json('/api/v1/register/', data)

        self.assertEqual(response.status_code, 201)
        response_data = response.json()
        self.assertEqual(response_data['username'], 'newstudent')
        self.assertEqual(response_data['role'], 'student')

        # Verifikasi data tersimpan di database
        self.assertTrue(User.objects.filter(username='newstudent').exists())

    def test_register_duplicate_username_fails(self):
        """
        Test registrasi dengan username yang sudah ada.

        Error path: username duplikat → HTTP 400 Bad Request.
        """
        data = {
            'username': 'instructor1',   # sudah ada di setUp()
            'password': 'TestPass123!',
            'email': 'unique@test.com',
            'first_name': 'Dup',
            'last_name': 'User',
            'role': 'student'
        }
        response = self.post_json('/api/v1/register/', data)
        self.assertEqual(response.status_code, 400)

    def test_register_duplicate_email_fails(self):
        """
        Test registrasi dengan email yang sudah ada.

        Error path: email duplikat → HTTP 400 Bad Request.
        """
        data = {
            'username': 'uniqueuser',
            'password': 'TestPass123!',
            'email': 'instructor1@test.com',   # sudah ada di setUp()
            'first_name': 'Dup',
            'last_name': 'Email',
            'role': 'student'
        }
        response = self.post_json('/api/v1/register/', data)
        self.assertEqual(response.status_code, 400)


# ==============================================================================
# TEST: LOGIN / AUTENTIKASI
# ==============================================================================

class TestLoginAPI(BaseLMSAPITest):
    """
    Integration test untuk endpoint POST /api/v1/auth/sign-in.

    Menguji JWT token generation melalui ninja-simple-jwt.
    """

    def test_login_with_correct_credentials_returns_token(self):
        """
        Test login dengan username dan password yang benar.

        Expected: HTTP 200, response berisi 'access' token.
        """
        response = self.post_json('/api/v1/auth/sign-in', {
            'username': 'student1',
            'password': 'StudPass1!'
        })

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn('access', data)
        self.assertTrue(len(data['access']) > 50)  # Token cukup panjang

    def test_login_with_wrong_password_fails(self):
        """
        Test login dengan password yang salah.

        Expected: HTTP 401 atau 400.
        """
        response = self.post_json('/api/v1/auth/sign-in', {
            'username': 'student1',
            'password': 'wrongpassword'
        })
        self.assertIn(response.status_code, [400, 401])

    def test_login_with_nonexistent_user_fails(self):
        """
        Test login dengan username yang tidak ada.

        Expected: HTTP 401 atau 400.
        """
        response = self.post_json('/api/v1/auth/sign-in', {
            'username': 'ghost_user',
            'password': 'AnyPass123!'
        })
        self.assertIn(response.status_code, [400, 401])


# ==============================================================================
# TEST: COURSE ENDPOINTS
# ==============================================================================

class TestCourseAPI(BaseLMSAPITest):
    """
    Integration test untuk CRUD operations Course.

    Menguji interaksi lengkap: HTTP → middleware → endpoint → database → response
    """

    def test_list_courses_is_public(self):
        """
        Test GET /api/v1/courses/ bisa diakses tanpa login.

        Daftar course adalah endpoint publik.
        """
        response = self.client.get('/api/v1/courses/')
        self.assertEqual(response.status_code, 200)

        # Harus mengembalikan list (ada 2 course dari setUp)
        data = response.json()
        self.assertIsInstance(data, list)
        self.assertGreaterEqual(len(data), 2)

    def test_list_courses_returns_correct_fields(self):
        """Test bahwa response course berisi field yang diharapkan."""
        response = self.client.get('/api/v1/courses/')
        data = response.json()

        if len(data) > 0:
            course = data[0]
            # Field-field wajib
            self.assertIn('id', course)
            self.assertIn('name', course)
            self.assertIn('price', course)
            self.assertIn('instructor', course)
            self.assertIn('created_at', course)

    def test_create_course_without_auth_fails(self):
        """
        Test POST /api/v1/courses/ tanpa token.

        Expected: HTTP 401 Unauthorized.
        """
        response = self.post_json('/api/v1/courses/', {
            'name': 'Unauthorized Course',
            'price': 100000
        })
        self.assertEqual(response.status_code, 401)

        # Pastikan course tidak tersimpan
        self.assertFalse(
            Course.objects.filter(name='Unauthorized Course').exists()
        )

    def test_create_course_as_instructor_success(self):
        """
        Test POST /api/v1/courses/ dengan token instructor.

        Happy path: instructor membuat course baru → HTTP 201.
        """
        token = self.get_token('instructor1', 'InstrPass1!')
        self.assertIsNotNone(token, "Login instructor1 gagal")

        response = self.post_json('/api/v1/courses/', {
            'name': 'Kursus Baru',
            'description': 'Deskripsi kursus baru',
            'price': 150000
        }, token=token)

        self.assertEqual(response.status_code, 201)
        data = response.json()
        self.assertEqual(data['name'], 'Kursus Baru')
        self.assertEqual(data['price'], 150000)

        # Verifikasi tersimpan di database
        self.assertTrue(
            Course.objects.filter(name='Kursus Baru').exists()
        )

    def test_get_course_detail(self):
        """Test GET /api/v1/courses/{id} mengembalikan detail course."""
        response = self.client.get(f'/api/v1/courses/{self.course1.id}')
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data['name'], 'Kursus Django Testing')

    def test_patch_course_by_owner(self):
        """
        Test PATCH /api/v1/courses/{id}/ — partial update oleh pemilik course.

        Hanya field yang dikirim yang berubah (exclude_unset=True).
        """
        token = self.get_token('instructor1', 'InstrPass1!')

        original_name = self.course1.name

        response = self.patch_json(
            f'/api/v1/courses/{self.course1.id}',
            {'price': 99000},
            token=token
        )

        self.assertEqual(response.status_code, 200)
        data = response.json()

        # Price berubah
        self.assertEqual(data['price'], 99000)
        # Name TIDAK berubah (tidak dikirim dalam request)
        self.assertEqual(data['name'], original_name)

    def test_delete_course_by_non_owner_forbidden(self):
        """
        Test DELETE /api/v1/courses/{id}/ oleh instructor lain.

        Pengujian negatif: instructor2 tidak bisa hapus course milik instructor1.
        Expected: HTTP 403 Forbidden.
        """
        token = self.get_token('instructor2', 'InstrPass2!')

        response = self.delete_req(
            f'/api/v1/courses/{self.course1.id}',
            token=token
        )

        self.assertEqual(response.status_code, 403)
        # Course masih ada
        self.assertTrue(Course.objects.filter(id=self.course1.id).exists())


# ==============================================================================
# TEST: ENROLLMENT ENDPOINTS
# ==============================================================================

class TestEnrollmentAPI(BaseLMSAPITest):
    """Integration test untuk enrollment (pendaftaran ke course)."""

    def test_student_enroll_to_course_success(self):
        """
        Test POST /api/v1/courses/{id}/enroll/ oleh student.

        Happy path: student belum terdaftar → enroll berhasil → HTTP 201.
        """
        token = self.get_token('student1', 'StudPass1!')

        response = self.post_json(
            f'/api/v1/courses/{self.course1.id}/enroll/',
            {},
            token=token
        )

        self.assertEqual(response.status_code, 201)

        # Verifikasi enrollment tersimpan di database
        self.assertTrue(
            Enrollment.objects.filter(
                student=self.student1,
                course=self.course1
            ).exists()
        )

    def test_student_cannot_enroll_twice(self):
        """
        Test student tidak bisa enroll dua kali ke course yang sama.

        Error path: sudah terdaftar → HTTP 400 Bad Request.
        """
        token = self.get_token('student1', 'StudPass1!')

        # Enroll pertama
        self.post_json(
            f'/api/v1/courses/{self.course1.id}/enroll/',
            {},
            token=token
        )

        # Enroll kedua — harus gagal
        response = self.post_json(
            f'/api/v1/courses/{self.course1.id}/enroll/',
            {},
            token=token
        )
        self.assertEqual(response.status_code, 400)

    def test_get_my_courses_returns_enrolled_courses(self):
        """
        Test GET /api/v1/mycourses/ mengembalikan daftar course yang diikuti.
        """
        # Enroll student1 ke course1 dan course2
        Enrollment.objects.create(student=self.student1, course=self.course1)
        Enrollment.objects.create(student=self.student1, course=self.course2)

        token = self.get_token('student1', 'StudPass1!')
        response = self.client.get(
            '/api/v1/mycourses/',
            HTTP_AUTHORIZATION=f'Bearer {token}'
        )

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(len(data), 2)


# ==============================================================================
# TEST: FILTER & API v2
# ==============================================================================

class TestFilterAPI(BaseLMSAPITest):
    """
    Integration test untuk FilterSchema dan API v2 pagination.

    Modul 10 features yang diverifikasi melalui integration test.
    """

    def test_filter_by_min_price(self):
        """
        Test GET /api/v1/courses/?min_price=250000

        Hanya course dengan harga >= 250000 yang dikembalikan.
        course1 = 200000 (tidak masuk)
        course2 = 300000 (masuk)
        """
        response = self.client.get('/api/v1/courses/?min_price=250000')
        self.assertEqual(response.status_code, 200)

        data = response.json()
        for course in data:
            self.assertGreaterEqual(
                course['price'], 250000,
                msg=f"Course {course['name']} harga {course['price']} < 250000"
            )

    def test_filter_by_max_price(self):
        """
        Test GET /api/v1/courses/?max_price=250000

        Hanya course dengan harga <= 250000 yang dikembalikan.
        """
        response = self.client.get('/api/v1/courses/?max_price=250000')
        self.assertEqual(response.status_code, 200)

        data = response.json()
        for course in data:
            self.assertLessEqual(
                course['price'], 250000,
                msg=f"Course {course['name']} harga {course['price']} > 250000"
            )

    def test_filter_by_search(self):
        """
        Test GET /api/v1/courses/?search=Django

        Hanya course yang namanya atau deskripsinya mengandung 'Django'.
        """
        response = self.client.get('/api/v1/courses/?search=Django')
        self.assertEqual(response.status_code, 200)

        data = response.json()
        # Pastikan ada hasil (course1 namanya mengandung 'Django')
        self.assertGreater(len(data), 0)

        # Semua hasil harus mengandung 'Django' di name atau description
        for course in data:
            contains_search = (
                'django' in course['name'].lower() or
                'django' in course['description'].lower()
            )
            self.assertTrue(
                contains_search,
                msg=f"Course '{course['name']}' tidak mengandung 'Django'"
            )

    def test_api_v2_returns_paginated_response(self):
        """
        Test GET /api/v2/courses/?page=1 mengembalikan format paginated.

        Format v2: {"items": [...], "count": N}
        Berbeda dengan v1 yang mengembalikan flat array.
        """
        response = self.client.get('/api/v2/courses/?page=1')
        self.assertEqual(response.status_code, 200)

        data = response.json()

        # Harus berformat paginated (items + count)
        self.assertIn('items', data)
        self.assertIn('count', data)
        self.assertIsInstance(data['items'], list)
        self.assertIsInstance(data['count'], int)

    def test_api_v2_course_has_member_count(self):
        """
        Test bahwa response v2 menyertakan field member_count.

        member_count = jumlah student yang enrolled ke course.
        """
        # Enroll student1 ke course1
        Enrollment.objects.create(student=self.student1, course=self.course1)

        response = self.client.get(f'/api/v2/courses/{self.course1.id}')
        self.assertEqual(response.status_code, 200)

        data = response.json()
        self.assertIn('member_count', data)
        self.assertEqual(data['member_count'], 1)
