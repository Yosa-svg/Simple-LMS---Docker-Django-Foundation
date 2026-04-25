"""
demo_query.py - Demonstrasi N+1 Problem dan Query Optimization

Script ini menunjukkan:
1. Masalah N+1 (banyak query karena akses relasi tanpa select_related)
2. Solusi dengan Custom Manager Course.objects.for_listing()
3. Solusi dengan Custom Manager Enrollment.objects.for_student_dashboard()
4. Perbandingan jumlah query

Cara menjalankan:
    docker-compose exec app python demo_query.py
"""

import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

# Aktifkan pelacakan query (DEBUG harus True di settings)
from django.conf import settings
settings.DEBUG = True  # Pastikan query logging aktif

from django.db import connection, reset_queries
from lms.models import Course, Enrollment, User


def separator(title):
    print("\n" + "=" * 60)
    print(f"  {title}")
    print("=" * 60)


def demo_n_plus_1():
    """
    DEMO 1: N+1 Problem
    -------------------------------------------------------
    Tanpa select_related, Django menjalankan 1 query untuk
    mengambil semua course, lalu 1 query LAGI per course
    untuk mengambil data instructor-nya.
    Jika ada N course -> N+1 total query (sangat tidak efisien!)
    """
    separator("DEMO 1: MASALAH N+1 (QUERY BIASA - LAMBAT 🐢)")
    reset_queries()

    courses = Course.objects.all()
    print(f"QuerySet dievaluasi, mengambil {courses.count()} courses...")
    reset_queries()  # Reset setelah count query

    for course in courses:
        # Setiap akses course.instructor menembak query BARU ke database!
        # Ini adalah N+1 problem.
        print(f"  Course: '{course.name}' | Instructor: {course.instructor.username}")

    total = len(connection.queries)
    print(f"\n>> TOTAL QUERY DATABASE: {total} queries")
    print(f"   (1 query untuk courses + {total - 1} query untuk setiap instructor)")


def demo_optimized_listing():
    """
    DEMO 2: Optimized dengan Course.objects.for_listing()
    -------------------------------------------------------
    Dengan select_related('instructor', 'category'), Django
    melakukan SQL JOIN di awal sehingga hanya 1 query untuk
    mengambil semua course BESERTA data instructor-nya.
    """
    separator("DEMO 2: OPTIMIZED LISTING (for_listing() - CEPAT 🚀)")
    reset_queries()

    # Custom manager: menggunakan select_related di balik layar
    courses = Course.objects.for_listing()
    for course in courses:
        # Data instructor sudah di-cache dari JOIN sebelumnya — NO extra query!
        category_name = course.category.name if course.category else 'Tanpa Kategori'
        print(f"  Course: '{course.name}' | Instructor: {course.instructor.username} | Kategori: {category_name}")

    total = len(connection.queries)
    print(f"\n>> TOTAL QUERY DATABASE: {total} queries")
    print(f"   (Hanya 1 query dengan JOIN, efisien untuk {Course.objects.count()} courses!)")


def demo_student_dashboard():
    """
    DEMO 3: Optimized Student Dashboard
    -------------------------------------------------------
    Menggunakan select_related + prefetch_related untuk
    mengambil semua data enrollment siswa beserta progress
    dalam jumlah query minimal.
    """
    separator("DEMO 3: STUDENT DASHBOARD (for_student_dashboard())")

    # Ambil satu student untuk demo
    student = User.objects.filter(role='student').first()
    if not student:
        print("  [SKIP] Tidak ada user dengan role 'student'.")
        print("  Buat dulu dengan: User.objects.create_user(..., role='student')")
        return

    reset_queries()

    enrollments = Enrollment.objects.for_student_dashboard(student)
    print(f"Dashboard untuk student: {student.username}")
    for enrollment in enrollments:
        progress_count = enrollment.progress_set.all().count()
        completed = enrollment.progress_set.filter(is_completed=True).count()
        print(f"  Course: '{enrollment.course.name}' | Progress: {completed}/{progress_count} materi selesai")

    total = len(connection.queries)
    print(f"\n>> TOTAL QUERY DATABASE: {total} queries (select_related + prefetch_related)")


def demo_perbandingan():
    """
    DEMO 4: Perbandingan langsung jumlah query
    """
    separator("DEMO 4: PERBANDINGAN JUMLAH QUERY")

    # --- Cara BURUK ---
    reset_queries()
    courses_bad = Course.objects.all()
    _ = [(c.name, c.instructor.username) for c in courses_bad]
    count_bad = len(connection.queries)

    # --- Cara BAIK ---
    reset_queries()
    courses_good = Course.objects.for_listing()
    _ = [(c.name, c.instructor.username) for c in courses_good]
    count_good = len(connection.queries)

    print(f"\n  {'Method':<35} {'Jumlah Query':>15}")
    print(f"  {'-'*50}")
    print(f"  {'Course.objects.all() (N+1)':<35} {count_bad:>14} query 🐢")
    print(f"  {'Course.objects.for_listing() (JOIN)':<35} {count_good:>14} query 🚀")

    if count_bad > 0:
        penghematan = round((1 - count_good / count_bad) * 100, 1)
        print(f"\n  >> Penghematan: {penghematan}% lebih sedikit query dengan for_listing()")


if __name__ == '__main__':
    print("\n" + "🔍 " * 20)
    print("  DEMO QUERY OPTIMIZATION - Simple LMS")
    print("  Pastikan ada data course di database terlebih dahulu!")
    print("🔍 " * 20)

    demo_n_plus_1()
    demo_optimized_listing()
    demo_student_dashboard()
    demo_perbandingan()

    print("\n" + "=" * 60)
    print("  Demo selesai! 🎉")
    print("=" * 60 + "\n")