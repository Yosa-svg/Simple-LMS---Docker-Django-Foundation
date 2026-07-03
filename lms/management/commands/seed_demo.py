"""
Seed command untuk membuat demo data di Simple LMS.

Membuat:
  - 3 akun demo (admin, instructor, student)
  - 5 course contoh dengan kategori berbeda
  - Enrollment student ke beberapa course
  - Konten course (CourseContent)
  - Progress belajar
  - Komentar contoh

Usage:
    docker-compose exec app python manage.py seed_demo
"""

from django.core.management.base import BaseCommand
from django.contrib.auth.hashers import make_password
from lms.models import User, Course, CourseMember, CourseContent, Comment, Enrollment


DEMO_ACCOUNTS = [
    {
        'username': 'admin_demo',
        'password': 'AdminDemo123!',
        'email': 'admin@lms.demo',
        'first_name': 'Admin',
        'last_name': 'Demo',
        'role': 'admin',
        'is_staff': True,
        'is_superuser': True,
    },
    {
        'username': 'instructor_demo',
        'password': 'InstrDemo123!',
        'email': 'instructor@lms.demo',
        'first_name': 'Budi',
        'last_name': 'Santoso',
        'role': 'instructor',
    },
    {
        'username': 'student_demo',
        'password': 'StudDemo123!',
        'email': 'student@lms.demo',
        'first_name': 'Ani',
        'last_name': 'Susanti',
        'role': 'student',
    },
]

DEMO_COURSES = [
    {
        'name': 'Python untuk Pemula',
        'description': 'Belajar Python dari nol hingga bisa membuat aplikasi sederhana. Cocok untuk mahasiswa semester 1.',
        'price': 150000,
        'level': 'beginner',
    },
    {
        'name': 'Django REST Framework',
        'description': 'Membangun REST API professional menggunakan Django dan Django Ninja. Integrasi database, auth, dan deployment.',
        'price': 250000,
        'level': 'intermediate',
    },
    {
        'name': 'Docker & DevOps Dasar',
        'description': 'Containerisasi aplikasi dengan Docker, Docker Compose, dan dasar-dasar CI/CD.',
        'price': 200000,
        'level': 'intermediate',
    },
    {
        'name': 'Database Design & PostgreSQL',
        'description': 'Desain database relasional, normalisasi, query optimization, dan PostgreSQL lanjutan.',
        'price': 180000,
        'level': 'intermediate',
    },
    {
        'name': 'Redis & Caching Strategies',
        'description': 'Implementasi caching, session management, rate limiting, dan pub/sub dengan Redis.',
        'price': 220000,
        'level': 'advanced',
    },
]

DEMO_CONTENTS = [
    'Pendahuluan dan Setup Environment',
    'Konsep Dasar',
    'Praktik: Hello World',
    'Studi Kasus',
    'Quiz dan Evaluasi',
]


class Command(BaseCommand):
    help = 'Membuat data demo untuk Simple LMS (akun, course, enrollment)'

    def add_arguments(self, parser):
        parser.add_argument(
            '--reset',
            action='store_true',
            help='Hapus data demo yang sudah ada sebelum membuat baru',
        )

    def handle(self, *args, **options):
        if options['reset']:
            self.stdout.write('🗑️  Menghapus data demo lama...')
            User.objects.filter(username__endswith='_demo').delete()
            Course.objects.filter(description__icontains='lms.demo').delete()
            self.stdout.write('✅ Data lama dihapus.')

        self.stdout.write('🌱 Membuat data demo Simple LMS...\n')

        # --- Buat akun demo ---
        users = {}
        for acc in DEMO_ACCOUNTS:
            username = acc['username']
            user, created = User.objects.get_or_create(
                username=username,
                defaults={
                    'email': acc['email'],
                    'first_name': acc['first_name'],
                    'last_name': acc['last_name'],
                    'role': acc.get('role', 'student'),
                    'is_staff': acc.get('is_staff', False),
                    'is_superuser': acc.get('is_superuser', False),
                }
            )
            if created:
                user.set_password(acc['password'])
                user.save()
                self.stdout.write(f'  ✅ User dibuat: {username} ({acc.get("role", "student")})')
            else:
                self.stdout.write(f'  ⏭️  User sudah ada: {username}')
            users[acc.get('role', 'student')] = user

        instructor = users.get('instructor')
        student = users.get('student')

        # --- Buat courses ---
        courses = []
        for course_data in DEMO_COURSES:
            course, created = Course.objects.get_or_create(
                name=course_data['name'],
                defaults={
                    'description': course_data['description'],
                    'price': course_data['price'],
                    'instructor': instructor,
                }
            )
            if created:
                self.stdout.write(f'  ✅ Course dibuat: {course.name}')
            else:
                self.stdout.write(f'  ⏭️  Course sudah ada: {course.name}')
            courses.append(course)

        # --- Buat course content ---
        for course in courses:
            for i, content_name in enumerate(DEMO_CONTENTS, 1):
                content_title = f'{i}. {content_name}'
                CourseContent.objects.get_or_create(
                    name=content_title,
                    course_id=course,
                )

        self.stdout.write(f'  ✅ Content dibuat untuk {len(courses)} course')

        # --- Enrollment student ke 3 course pertama ---
        for course in courses[:3]:
            enrollment, created = Enrollment.objects.get_or_create(
                student=student,
                course=course,
            )
            if created:
                # Buat CourseMember (dibutuhkan untuk komentar)
                member, _ = CourseMember.objects.get_or_create(
                    course_id=course,
                    user_id=student,
                    defaults={'roles': 'std'},
                )
                # Tambahkan komentar di content pertama
                content = course.coursecontent_set.first()
                if content and member:
                    Comment.objects.get_or_create(
                        content_id=content,
                        member_id=member,
                        defaults={'comment': f'Materi {course.name} sangat membantu!'},
                    )
                self.stdout.write(f'  ✅ Enrollment: {student.username} → {course.name}')

        # --- Instructor sebagai CourseMember di semua course-nya ---
        for course in courses:
            CourseMember.objects.get_or_create(
                course_id=course,
                user_id=instructor,
                defaults={'roles': 'ins'},
            )

        self.stdout.write('\n' + '='*60)
        self.stdout.write('🎉 DATA DEMO BERHASIL DIBUAT!')
        self.stdout.write('='*60)
        self.stdout.write('\n📋 AKUN DEMO:')
        self.stdout.write('  👑 Admin    : admin_demo / AdminDemo123!')
        self.stdout.write('  👨‍🏫 Instructor: instructor_demo / InstrDemo123!')
        self.stdout.write('  👨‍🎓 Student  : student_demo / StudDemo123!')
        self.stdout.write('\n📚 COURSES YANG DIBUAT:')
        for i, c in enumerate(DEMO_COURSES, 1):
            self.stdout.write(f'  {i}. {c["name"]} (Rp {c["price"]:,})')
        self.stdout.write('\n🔑 Login via API:')
        self.stdout.write('  POST /api/v1/auth/sign-in')
        self.stdout.write('  {"username": "student_demo", "password": "StudDemo123!"}\n')
