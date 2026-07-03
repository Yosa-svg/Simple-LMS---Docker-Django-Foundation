"""
generate_data.py - Script untuk generate data testing dalam jumlah besar

Digunakan untuk memenuhi syarat lab: minimal 100 courses agar N+1 terlihat nyata.

Cara menjalankan:
    docker-compose exec app python generate_data.py

Apa yang dibuat:
    - 2 instructor tambahan (jika belum ada)
    - 100 courses (batch insert via bulk_create)
    - 500 course members (bulk_create)
    - 300 course contents (bulk_create)
    - 1000 comments (bulk_create)

Catatan:
    - Aman dijalankan berulang kali (skip jika data sudah ada)
    - Gunakan setelah migrate dan importer.py sudah berjalan
"""

import os
import random
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from django.db import connection
from lms.models import User, Category, Course, CourseMember, CourseContent, Comment


def separator(msg):
    print(f"\n{'─'*55}")
    print(f"  {msg}")
    print('─'*55)


# ── 1. Pastikan ada instructor ────────────────────────────────────────────────

def ensure_instructors():
    separator("Memastikan minimal 2 instructor tersedia")
    instructors = []
    for i in range(1, 3):
        user, created = User.objects.get_or_create(
            username=f'dosen{i:02d}',
            defaults={
                'email': f'dosen{i:02d}@lms.id',
                'first_name': f'Dosen',
                'last_name': f'{i:02d}',
                'role': 'instructor',
            }
        )
        if created:
            user.set_password('dosen123')
            user.save()
            print(f"  [CREATED] instructor: {user.username}")
        else:
            print(f"  [EXISTS]  instructor: {user.username}")
        instructors.append(user)
    return instructors


# ── 2. Pastikan ada category ──────────────────────────────────────────────────

def ensure_category():
    cat, _ = Category.objects.get_or_create(name='Umum', defaults={'parent': None})
    return cat


# ── 3. Generate 100 Courses (bulk_create) ─────────────────────────────────────

def generate_courses(instructors, category, target=100):
    separator(f"Generating Courses (target: {target})")
    existing = Course.objects.count()
    if existing >= target:
        print(f"  [SKIP] Sudah ada {existing} courses (target {target} tercapai)")
        return list(Course.objects.all())

    needed = target - existing
    print(f"  Membuat {needed} courses baru (sudah ada {existing})...")

    topics = [
        'Pengantar', 'Lanjutan', 'Dasar', 'Mahir', 'Praktis',
        'Teori', 'Implementasi', 'Workshop', 'Bootcamp', 'Intensif'
    ]
    subjects = [
        'Python', 'JavaScript', 'Django', 'React', 'SQL', 'Docker',
        'Kubernetes', 'Machine Learning', 'Data Science', 'DevOps',
        'Algoritma', 'Struktur Data', 'Jaringan', 'Keamanan', 'Cloud',
        'API', 'Testing', 'Git', 'Linux', 'PostgreSQL'
    ]

    new_courses = []
    for i in range(needed):
        topic = random.choice(topics)
        subject = random.choice(subjects)
        instructor = random.choice(instructors)
        price = random.choice([50000, 75000, 100000, 125000, 150000, 200000])

        new_courses.append(Course(
            name=f'{topic} {subject} #{existing + i + 1}',
            description=f'Pelajari {subject} dari dasar hingga mahir. Kursus {topic} yang komprehensif.',
            price=price,
            instructor=instructor,
            category=category,
        ))

    # bulk_create: 1 query untuk N records!
    created = Course.objects.bulk_create(new_courses, batch_size=500)
    print(f"  [DONE] bulk_create {len(created)} courses dalam 1 query  🚀")
    return list(Course.objects.all())


# ── 4. Generate Course Members (bulk_create) ──────────────────────────────────

def generate_members(courses, target_per_course=5):
    separator(f"Generating CourseMember (~{target_per_course} per course)")

    # Pastikan ada students
    students = list(User.objects.filter(role='student'))
    if len(students) < 10:
        print(f"  Membuat students sampai total 10...")
        for i in range(len(students) + 1, 11):
            user, created = User.objects.get_or_create(
                username=f'siswa{i:02d}',
                defaults={
                    'email': f'siswa{i:02d}@lms.id',
                    'first_name': 'Siswa',
                    'last_name': f'{i:02d}',
                    'role': 'student',
                }
            )
            if created:
                user.set_password('siswa123')
                user.save()
        students = list(User.objects.filter(role='student'))

    existing_count = CourseMember.objects.count()
    print(f"  CourseMember saat ini: {existing_count}")

    new_members = []
    existing_pairs = set(
        CourseMember.objects.values_list('course_id_id', 'user_id_id')
    )

    for course in courses:
        sample_size = min(target_per_course, len(students))
        sampled = random.sample(students, sample_size)
        for idx, student in enumerate(sampled):
            pair = (course.pk, student.pk)
            if pair not in existing_pairs:
                role = 'ast' if idx == 0 and random.random() < 0.2 else 'std'
                new_members.append(CourseMember(
                    course_id=course,
                    user_id=student,
                    roles=role,
                ))
                existing_pairs.add(pair)

    if new_members:
        CourseMember.objects.bulk_create(new_members, batch_size=500, ignore_conflicts=True)
        print(f"  [DONE] bulk_create {len(new_members)} members dalam ~1 query  🚀")
    else:
        print(f"  [SKIP] Tidak ada member baru yang perlu ditambahkan")


# ── 5. Generate Course Contents (bulk_create) ─────────────────────────────────

def generate_contents(courses, contents_per_course=3):
    separator(f"Generating CourseContent (~{contents_per_course} per course)")
    existing_count = CourseContent.objects.count()
    print(f"  CourseContent saat ini: {existing_count}")

    existing_course_ids = set(
        CourseContent.objects.values_list('course_id_id', flat=True).distinct()
    )

    new_contents = []
    for course in courses:
        if course.pk in existing_course_ids:
            continue
        for j in range(1, contents_per_course + 1):
            new_contents.append(CourseContent(
                name=f'Modul {j} - {course.name}',
                description=f'Materi modul ke-{j} dari course {course.name}.',
                video_url=f'https://youtube.com/watch?v=demo_{course.pk}_{j}',
                course_id=course,
            ))

    if new_contents:
        CourseContent.objects.bulk_create(new_contents, batch_size=500)
        print(f"  [DONE] bulk_create {len(new_contents)} contents dalam ~1 query  🚀")
    else:
        print(f"  [SKIP] Contents sudah ada untuk semua course")


# ── 6. Generate Comments (bulk_create) ────────────────────────────────────────

def generate_comments(target=1000):
    separator(f"Generating Comments (target: {target} total)")
    existing = Comment.objects.count()
    if existing >= target:
        print(f"  [SKIP] Sudah ada {existing} comments (target {target} tercapai)")
        return

    needed = target - existing
    print(f"  Membuat {needed} comments baru...")

    contents = list(CourseContent.objects.select_related('course_id'))
    members = list(CourseMember.objects.select_related('user_id', 'course_id'))

    if not contents or not members:
        print("  [ERROR] Tidak ada content atau member. Jalankan generate_contents dulu.")
        return

    sample_texts = [
        'Materi ini sangat bermanfaat!',
        'Penjelasan sangat jelas dan mudah dipahami.',
        'Tolong tambahkan lebih banyak contoh praktis.',
        'Bagus sekali, langsung bisa dipraktikkan.',
        'Ada yang bisa membantu soal nomor 3?',
        'Terima kasih, materi ini sangat membantu project saya.',
        'Apakah ada referensi buku yang direkomendasikan?',
        'Sudah coba tapi error, bisa dibantu?',
        'Mantap! Langsung paham.',
        'Konsepnya unik, belum pernah tahu sebelumnya.',
    ]

    new_comments = []
    for _ in range(needed):
        content = random.choice(contents)
        # Cari member dari course yang sama
        matching = [m for m in members if m.course_id_id == content.course_id_id]
        if not matching:
            continue
        member = random.choice(matching)
        new_comments.append(Comment(
            content_id=content,
            member_id=member,
            comment=random.choice(sample_texts),
        ))

    if new_comments:
        Comment.objects.bulk_create(new_comments, batch_size=500)
        print(f"  [DONE] bulk_create {len(new_comments)} comments dalam ~1 query  🚀")


# ── Main ──────────────────────────────────────────────────────────────────────

if __name__ == '__main__':
    print("\n" + "🔥 " * 18)
    print("  SIMPLE LMS - BULK DATA GENERATOR")
    print("  Membuat data testing untuk Lab Query Optimization...")
    print("🔥 " * 18)

    instructors = ensure_instructors()
    category = ensure_category()
    courses = generate_courses(instructors, category, target=100)
    generate_members(courses, target_per_course=5)
    generate_contents(courses, contents_per_course=3)
    generate_comments(target=1000)

    print(f"\n{'='*55}")
    print(f"  ✅ Data generation selesai!")
    print(f"  📊 Summary:")
    print(f"     Users      : {User.objects.count()}")
    print(f"     Courses    : {Course.objects.count()}")
    print(f"     Members    : {CourseMember.objects.count()}")
    print(f"     Contents   : {CourseContent.objects.count()}")
    print(f"     Comments   : {Comment.objects.count()}")
    print(f"\n  Sekarang akses endpoint lab untuk melihat N+1 di Silk:")
    print(f"  http://localhost:8000/lab/course-list/baseline/")
    print(f"  http://localhost:8000/silk/")
    print(f"{'='*55}\n")
