"""
importer.py - Script untuk mengimpor data awal (seed data) dari file CSV

Mengimpor data: Users, Categories, Courses, CourseMember (anggota kelas)

Cara menjalankan:
    docker-compose exec app python importer.py

Catatan:
    - Script ini aman untuk dijalankan berulang kali (idempotent)
      karena menggunakan get_or_create()
    - Jalankan SETELAH migrate dan createsuperuser
"""

import csv
import django
import os

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from lms.models import User, Category, Course, CourseMember


# ── Helper ──────────────────────────────────────────────────────────────────

def print_section(title):
    print(f"\n{'='*55}")
    print(f"  {title}")
    print('='*55)


# ── 1. Import Users ──────────────────────────────────────────────────────────

def import_users(csv_file='fixtures/users.csv'):
    """Import data user dari CSV. Lewati jika username sudah ada."""
    print_section("1. IMPORTING USERS")
    try:
        with open(csv_file, newline='', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                user, created = User.objects.get_or_create(
                    username=row['username'],
                    defaults={
                        'email': row['email'],
                        'first_name': row['first_name'],
                        'last_name': row['last_name'],
                        'role': row['role'],
                    }
                )
                if created:
                    user.set_password(row['password'])
                    # Admin mendapatkan akses staff dan superuser
                    if row['role'] == 'admin':
                        user.is_staff = True
                        user.is_superuser = True
                    user.save()
                    print(f"  [CREATED] {row['role'].upper()}: {user.username} ({user.get_full_name()})")
                else:
                    print(f"  [EXISTS]  {user.role.upper()}: {user.username}")
    except FileNotFoundError:
        print(f"  [ERROR] File tidak ditemukan: {csv_file}")


# ── 2. Import Categories ─────────────────────────────────────────────────────

def import_categories(csv_file='fixtures/categories.csv'):
    """
    Import data kategori dari CSV.
    Mendukung hierarki: parent dibuat lebih dulu, lalu child.
    """
    print_section("2. IMPORTING CATEGORIES")
    try:
        with open(csv_file, newline='', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            rows = list(reader)

        # Dua pass: pertama root categories, lalu sub-categories
        for row in rows:
            if not row['parent_name']:  # Root category
                cat, created = Category.objects.get_or_create(
                    name=row['name'],
                    defaults={'parent': None}
                )
                if created:
                    print(f"  [CREATED] Kategori Root: {cat.name}")
                else:
                    print(f"  [EXISTS]  Kategori Root: {cat.name}")

        for row in rows:
            if row['parent_name']:  # Sub-category
                try:
                    parent = Category.objects.get(name=row['parent_name'])
                    cat, created = Category.objects.get_or_create(
                        name=row['name'],
                        defaults={'parent': parent}
                    )
                    if created:
                        print(f"  [CREATED] Sub-kategori: {row['parent_name']} > {cat.name}")
                    else:
                        print(f"  [EXISTS]  Sub-kategori: {row['parent_name']} > {cat.name}")
                except Category.DoesNotExist:
                    print(f"  [ERROR]   Parent '{row['parent_name']}' tidak ditemukan untuk '{row['name']}'")
    except FileNotFoundError:
        print(f"  [ERROR] File tidak ditemukan: {csv_file}")


# ── 3. Import Courses ────────────────────────────────────────────────────────

def import_courses(csv_file='fixtures/courses.csv'):
    """Import data course dari CSV."""
    print_section("3. IMPORTING COURSES")
    try:
        with open(csv_file, newline='', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                try:
                    instructor = User.objects.get(username=row['instructor_username'])
                except User.DoesNotExist:
                    print(f"  [ERROR] Instructor '{row['instructor_username']}' tidak ditemukan. Lewati.")
                    continue

                category = None
                if row.get('category_name'):
                    try:
                        category = Category.objects.get(name=row['category_name'])
                    except Category.DoesNotExist:
                        print(f"  [WARN]  Kategori '{row['category_name']}' tidak ditemukan, course dibuat tanpa kategori.")

                course, created = Course.objects.get_or_create(
                    name=row['name'],
                    defaults={
                        'description': row['description'],
                        'price': int(row['price']),
                        'instructor': instructor,
                        'category': category,
                    }
                )
                if created:
                    print(f"  [CREATED] Course: '{course.name}' (Rp{course.price:,}) | Instructor: {instructor.username}")
                else:
                    print(f"  [EXISTS]  Course: '{course.name}'")
    except FileNotFoundError:
        print(f"  [ERROR] File tidak ditemukan: {csv_file}")


# ── 4. Import CourseMember ───────────────────────────────────────────────────

def import_members(csv_file='fixtures/members.csv'):
    """Import data anggota kelas (CourseMember) dari CSV."""
    print_section("4. IMPORTING COURSE MEMBERS")
    try:
        with open(csv_file, newline='', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                try:
                    course = Course.objects.get(name=row['course_name'])
                    user = User.objects.get(username=row['username'])
                except (Course.DoesNotExist, User.DoesNotExist) as e:
                    print(f"  [ERROR] {e}. Lewati baris: {row}")
                    continue

                member, created = CourseMember.objects.get_or_create(
                    course_id=course,
                    user_id=user,
                    defaults={'roles': row['roles']}
                )
                if created:
                    print(f"  [CREATED] {user.username} -> '{course.name}' sebagai {member.get_roles_display()}")
                else:
                    print(f"  [EXISTS]  {user.username} -> '{course.name}'")
    except FileNotFoundError:
        print(f"  [ERROR] File tidak ditemukan: {csv_file}")


# ── Main ─────────────────────────────────────────────────────────────────────

if __name__ == '__main__':
    print("\n" + "🚀 " * 18)
    print("  SIMPLE LMS - DATA IMPORTER")
    print("  Mengimpor data awal dari file CSV...")
    print("🚀 " * 18)

    import_users()
    import_categories()
    import_courses()
    import_members()

    print(f"\n{'='*55}")
    print("  ✅ Import selesai!")
    print(f"{'='*55}\n")
