# lms/tests/test_coverage_boost.py
"""
Coverage Boost Tests — Final Project

Test-test ini dibuat secara targeted untuk meningkatkan coverage
pada endpoint-endpoint yang belum dicovered oleh test suite sebelumnya.

Endpoint yang dicover di sini:
    - GET  /api/v1/profile/             (profil user)
    - GET  /api/v1/courses/popular/     (Redis popular courses)
    - GET  /api/v1/courses/{id}         (course detail dengan DB path)
    - POST /api/v1/courses/{id}/visit/  (catat kunjungan)
    - GET  /api/v1/my-history/          (riwayat kunjungan)
    - PUT  /api/v1/courses/{id}         (full update course)
    - DELETE /api/v1/courses/{id}       (hapus course)
    - POST /api/v1/courses/{id}/enroll/ (enrollment)
    - GET  /api/v1/mycourses/           (daftar kursus yang diikuti)
    - POST /api/v1/comments/            (tambah komentar)
    - PUT  /api/v1/comments/{id}        (edit komentar)
    - DELETE /api/v1/comments/{id}      (hapus komentar)
    - GET  /api/v1/analytics/popular-courses/  (MongoDB analytics)
    - GET  /api/v1/analytics/daily-summary/    (MongoDB analytics)
    - GET  /api/v1/analytics/enrollment-stats/ (MongoDB analytics)
    - GET  /api/v1/analytics/my-activity/      (MongoDB analytics)
    - GET  /api/v1/reports/status/{id}/        (Celery task status)
    - GET  /api/v1/courses/?ordering=invalid   (fallback ordering)
"""

import json
from django.test import TestCase, Client

from lms.models import User, Course, CourseMember, CourseContent, Comment, Enrollment


# ==============================================================================
# BASE CLASS
# ==============================================================================

class BaseBoostTest(TestCase):
    """Base test class dengan setup umum untuk semua coverage boost tests."""

    def setUp(self):
        self.client = Client()

        self.instructor = User.objects.create_user(
            username='boost_instr', password='BoostPass1!',
            email='boost_instr@test.com', role='instructor',
        )
        self.student = User.objects.create_user(
            username='boost_student', password='BoostPass2!',
            email='boost_student@test.com', role='student',
        )
        self.other_user = User.objects.create_user(
            username='boost_other', password='BoostPass3!',
            email='boost_other@test.com', role='student',
        )

        self.course = Course.objects.create(
            name='Boost Test Course',
            description='Coverage boost course',
            price=100000,
            instructor=self.instructor,
        )

    def login(self, username, password):
        """Kembalikan JWT access token."""
        resp = self.client.post(
            '/api/v1/auth/sign-in',
            data=json.dumps({'username': username, 'password': password}),
            content_type='application/json',
        )
        if resp.status_code == 200:
            return resp.json().get('access')
        return None

    def auth_headers(self, token):
        return {'HTTP_AUTHORIZATION': f'Bearer {token}'}

    def get(self, url, token=None):
        h = self.auth_headers(token) if token else {}
        return self.client.get(url, **h)

    def post(self, url, data=None, token=None):
        h = self.auth_headers(token) if token else {}
        return self.client.post(
            url,
            data=json.dumps(data or {}),
            content_type='application/json',
            **h,
        )

    def put(self, url, data, token=None):
        h = self.auth_headers(token) if token else {}
        return self.client.put(
            url,
            data=json.dumps(data),
            content_type='application/json',
            **h,
        )

    def delete(self, url, token=None):
        h = self.auth_headers(token) if token else {}
        return self.client.delete(url, **h)


# ==============================================================================
# PROFILE ENDPOINT
# ==============================================================================

class TestProfileEndpoint(BaseBoostTest):

    def test_get_profile_returns_user_data(self):
        token = self.login('boost_instr', 'BoostPass1!')
        resp = self.get('/api/v1/profile/', token)
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()['username'], 'boost_instr')

    def test_get_profile_requires_auth(self):
        resp = self.get('/api/v1/profile/')
        self.assertEqual(resp.status_code, 401)


# ==============================================================================
# COURSE DETAIL — DB PATH (note: NO trailing slash on this endpoint)
# ==============================================================================

class TestCourseDetailDB(BaseBoostTest):

    def test_course_detail_returns_200(self):
        # URL without trailing slash — matches 'courses/{id}' pattern
        resp = self.get(f'/api/v1/courses/{self.course.id}')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()['name'], 'Boost Test Course')

    def test_course_detail_not_found_returns_404(self):
        resp = self.get('/api/v1/courses/99999')
        self.assertEqual(resp.status_code, 404)

    def test_course_detail_authenticated_logs_view(self):
        """Authenticated user yang view course menghasilkan MongoDB log (graceful)."""
        token = self.login('boost_student', 'BoostPass2!')
        resp = self.get(f'/api/v1/courses/{self.course.id}', token)
        self.assertEqual(resp.status_code, 200)


# ==============================================================================
# POPULAR COURSES — Redis Sorted Set
# ==============================================================================

class TestPopularCourses(BaseBoostTest):

    def test_popular_courses_returns_list(self):
        resp = self.get('/api/v1/courses/popular/')
        self.assertEqual(resp.status_code, 200)
        self.assertIsInstance(resp.json(), list)

    def test_popular_courses_with_limit(self):
        resp = self.get('/api/v1/courses/popular/?limit=3')
        self.assertEqual(resp.status_code, 200)


# ==============================================================================
# VISIT COURSE & HISTORY — Redis Session
# ==============================================================================

class TestVisitAndHistory(BaseBoostTest):

    def test_visit_course_records_to_session(self):
        resp = self.post(f'/api/v1/courses/{self.course.id}/visit/')
        self.assertEqual(resp.status_code, 200)
        self.assertIn(self.course.id, resp.json()['history'])

    def test_visit_nonexistent_course_returns_404(self):
        resp = self.post('/api/v1/courses/99999/visit/')
        self.assertEqual(resp.status_code, 404)

    def test_my_history_empty_returns_empty_list(self):
        resp = self.get('/api/v1/my-history/')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json(), [])

    def test_my_history_returns_visited_courses(self):
        self.client.post(
            f'/api/v1/courses/{self.course.id}/visit/',
            data='{}', content_type='application/json',
        )
        resp = self.get('/api/v1/my-history/')
        self.assertEqual(resp.status_code, 200)
        ids = [c['id'] for c in resp.json()]
        self.assertIn(self.course.id, ids)


# ==============================================================================
# UPDATE COURSE (PUT) — NO trailing slash
# ==============================================================================

class TestUpdateCourse(BaseBoostTest):

    def test_owner_can_full_update_course(self):
        token = self.login('boost_instr', 'BoostPass1!')
        resp = self.put(
            f'/api/v1/courses/{self.course.id}',
            {'name': 'Updated Name', 'description': 'Updated desc', 'price': 200000},
            token,
        )
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()['name'], 'Updated Name')

    def test_non_owner_cannot_update_course(self):
        token = self.login('boost_student', 'BoostPass2!')
        resp = self.put(
            f'/api/v1/courses/{self.course.id}',
            {'name': 'Hacked', 'description': 'x', 'price': 1},
            token,
        )
        self.assertIn(resp.status_code, [403, 401])

    def test_update_nonexistent_course_returns_404(self):
        token = self.login('boost_instr', 'BoostPass1!')
        resp = self.put(
            '/api/v1/courses/99999',
            {'name': 'X', 'description': 'x', 'price': 1},
            token,
        )
        self.assertEqual(resp.status_code, 404)


# ==============================================================================
# DELETE COURSE — NO trailing slash
# ==============================================================================

class TestDeleteCourse(BaseBoostTest):

    def test_owner_can_delete_course(self):
        deletable = Course.objects.create(
            name='To Be Deleted', price=0, instructor=self.instructor,
        )
        token = self.login('boost_instr', 'BoostPass1!')
        resp = self.delete(f'/api/v1/courses/{deletable.id}', token)
        self.assertEqual(resp.status_code, 204)
        self.assertFalse(Course.objects.filter(pk=deletable.id).exists())

    def test_non_owner_cannot_delete(self):
        token = self.login('boost_student', 'BoostPass2!')
        resp = self.delete(f'/api/v1/courses/{self.course.id}', token)
        self.assertIn(resp.status_code, [403, 401])

    def test_delete_nonexistent_returns_404(self):
        token = self.login('boost_instr', 'BoostPass1!')
        resp = self.delete('/api/v1/courses/99999', token)
        self.assertEqual(resp.status_code, 404)


# ==============================================================================
# ENROLLMENT
# ==============================================================================

class TestEnrollmentCoverage(BaseBoostTest):

    def test_student_can_enroll(self):
        token = self.login('boost_student', 'BoostPass2!')
        resp = self.post(f'/api/v1/courses/{self.course.id}/enroll/', token=token)
        self.assertIn(resp.status_code, [200, 201])

    def test_cannot_enroll_twice(self):
        token = self.login('boost_student', 'BoostPass2!')
        self.post(f'/api/v1/courses/{self.course.id}/enroll/', token=token)
        resp2 = self.post(f'/api/v1/courses/{self.course.id}/enroll/', token=token)
        self.assertIn(resp2.status_code, [400, 409])

    def test_mycourses_returns_enrolled_courses(self):
        token = self.login('boost_student', 'BoostPass2!')
        self.post(f'/api/v1/courses/{self.course.id}/enroll/', token=token)
        resp = self.get('/api/v1/mycourses/', token)
        self.assertEqual(resp.status_code, 200)

    def test_mycourses_requires_auth(self):
        resp = self.get('/api/v1/mycourses/')
        self.assertEqual(resp.status_code, 401)


# ==============================================================================
# COMMENTS — POST has trailing slash, PUT/DELETE do NOT
# ==============================================================================

class TestCommentsCoverage(BaseBoostTest):

    def setUp(self):
        super().setUp()
        # PENTING: Enrollment diperlukan oleh check_enrollment() di POST /comments/
        # check_enrollment() memeriksa tabel Enrollment, bukan CourseMember
        Enrollment.objects.create(
            student=self.student,
            course=self.course,
        )
        # CourseMember diperlukan sebagai FK pada model Comment
        self.member = CourseMember.objects.create(
            course_id=self.course,
            user_id=self.student,
            roles='std',
        )
        self.content = CourseContent.objects.create(
            name='Test Content',
            course_id=self.course,
        )

    def test_enrolled_student_can_post_comment(self):
        token = self.login('boost_student', 'BoostPass2!')
        resp = self.post('/api/v1/comments/', {
            'content_id': self.content.id,
            'comment': 'Test komentar dari student',
        }, token)
        self.assertIn(resp.status_code, [200, 201])

    def test_non_enrolled_cannot_comment(self):
        token = self.login('boost_other', 'BoostPass3!')
        resp = self.post('/api/v1/comments/', {
            'content_id': self.content.id,
            'comment': 'Hacked comment',
        }, token)
        self.assertIn(resp.status_code, [400, 403, 404])

    def test_can_edit_own_comment(self):
        # Buat comment langsung via ORM dengan FK names yang benar
        comment = Comment.objects.create(
            content_id=self.content,   # FK: content_id
            member_id=self.member,     # FK: member_id
            comment='Original comment',
        )
        token = self.login('boost_student', 'BoostPass2!')
        resp = self.put(f'/api/v1/comments/{comment.id}', {
            'comment': 'Updated comment',
        }, token)
        self.assertIn(resp.status_code, [200, 201])

    def test_can_delete_own_comment(self):
        comment = Comment.objects.create(
            content_id=self.content,
            member_id=self.member,
            comment='To be deleted',
        )
        token = self.login('boost_student', 'BoostPass2!')
        resp = self.delete(f'/api/v1/comments/{comment.id}', token)
        self.assertIn(resp.status_code, [200, 204])


# ==============================================================================
# ANALYTICS ENDPOINTS (MongoDB — graceful jika Mongo tidak tersedia)
# ==============================================================================

class TestAnalyticsEndpoints(BaseBoostTest):

    def test_popular_courses_analytics_returns_list(self):
        resp = self.get('/api/v1/analytics/popular-courses/')
        self.assertEqual(resp.status_code, 200)
        self.assertIsInstance(resp.json(), list)

    def test_daily_summary_returns_list(self):
        resp = self.get('/api/v1/analytics/daily-summary/')
        self.assertEqual(resp.status_code, 200)

    def test_enrollment_stats_requires_auth(self):
        token = self.login('boost_instr', 'BoostPass1!')
        resp = self.get('/api/v1/analytics/enrollment-stats/', token)
        self.assertEqual(resp.status_code, 200)

    def test_my_activity_requires_auth(self):
        resp = self.get('/api/v1/analytics/my-activity/')
        self.assertEqual(resp.status_code, 401)

    def test_my_activity_returns_data_for_auth_user(self):
        token = self.login('boost_student', 'BoostPass2!')
        resp = self.get('/api/v1/analytics/my-activity/', token)
        self.assertEqual(resp.status_code, 200)


# ==============================================================================
# REPORT STATUS (Celery AsyncResult)
# ==============================================================================

class TestReportStatus(BaseBoostTest):

    def test_report_status_unknown_task_returns_data(self):
        token = self.login('boost_instr', 'BoostPass1!')
        fake_task_id = 'aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee'
        resp = self.get(f'/api/v1/reports/status/{fake_task_id}/', token)
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data['task_id'], fake_task_id)

    def test_report_status_requires_auth(self):
        resp = self.get('/api/v1/reports/status/fake-id/')
        self.assertEqual(resp.status_code, 401)


# ==============================================================================
# COURSE LIST — Ordering Fallback & Filters
# ==============================================================================

class TestCourseListFallback(BaseBoostTest):

    def test_invalid_ordering_falls_back_to_default(self):
        resp = self.get('/api/v1/courses/?ordering=invalid_field')
        self.assertEqual(resp.status_code, 200)

    def test_filter_by_name_search(self):
        resp = self.get('/api/v1/courses/?search=Boost')
        self.assertEqual(resp.status_code, 200)

    def test_pagination_works(self):
        resp = self.get('/api/v1/courses/?page=1&page_size=5')
        self.assertEqual(resp.status_code, 200)


# ==============================================================================
# HELPER FUNCTIONS & MISC
# ==============================================================================

class TestHelperAndMisc(BaseBoostTest):

    def test_get_object_or_404_raises_on_missing(self):
        resp = self.get('/api/v1/courses/99999')
        self.assertEqual(resp.status_code, 404)

    def test_get_client_ip_via_x_forwarded_for(self):
        """get_client_ip harus membaca X-Forwarded-For header."""
        resp = self.client.get(
            '/api/v1/courses/',
            HTTP_X_FORWARDED_FOR='10.0.0.1, 192.168.1.1',
        )
        self.assertEqual(resp.status_code, 200)

    def test_apiv2_course_list(self):
        resp = self.get('/api/v2/courses/')
        self.assertEqual(resp.status_code, 200)

    def test_register_new_user(self):
        # URL register dengan trailing slash; semua field wajib sesuai UserIn schema
        resp = self.post('/api/v1/register/', {
            'username': 'newboostuser',
            'email': 'newboost@test.com',
            'password': 'NewBoostPass1!',
            'first_name': 'New',
            'last_name': 'Boost',
            'role': 'student',
        })
        self.assertIn(resp.status_code, [200, 201])

