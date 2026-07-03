# locustfile.py
"""
Load Testing Script untuk Simple LMS — Modul 11

Menggunakan Locust (https://locust.io) untuk mensimulasikan banyak user
yang mengakses API secara bersamaan dan mengukur performa.

INSTALASI (di host, bukan di Docker):
    pip install locust

CARA MENJALANKAN:
    # Mode Web UI (buka browser http://localhost:8089)
    locust -f locustfile.py --host=http://localhost:8000

    # Mode headless (tanpa browser) — 20 users, 2/detik, durasi 30 detik
    locust -f locustfile.py --host=http://localhost:8000 \
        --headless --users 20 --spawn-rate 2 --run-time 30s

    # Export hasil ke CSV
    locust -f locustfile.py --host=http://localhost:8000 \
        --headless --users 20 --spawn-rate 2 --run-time 60s \
        --csv=results/load_test_report

METRIK YANG DIAMATI:
    - Response Time (avg, min, max, P95)
    - Request Per Second (throughput)
    - Error Rate (target: < 1%)
    - Concurrent Users
"""

from locust import HttpUser, task, between


class LMSUser(HttpUser):
    """
    Simulasi user yang mengakses Simple LMS API.

    Setiap LMSUser merepresentasikan satu user nyata dengan pola akses:
    - Lebih sering membaca (GET) daripada menulis (POST/PATCH)
    - Ada delay antara aksi (1-3 detik, seperti user manusia)

    Weight system:
        @task(3) = 3x lebih sering dari @task(1)
        Distribusi: get_courses(3) + get_course_detail(2) + get_courses_v2(2)
                    + view_profile(1) + post_comment(1) + filter_courses(1)
        Total weight = 10
    """

    # Simulasi waktu berpikir user (1-3 detik antar aksi)
    wait_time = between(1, 3)

    # Menyimpan token JWT setelah login
    access_token = None
    # Menyimpan course_id yang akan diakses
    course_id = 1

    def on_start(self):
        """
        Dipanggil saat setiap simulated user mulai.

        Setiap user harus login terlebih dahulu untuk mendapatkan token.
        Jika login gagal, user tetap bisa mengakses endpoint publik.
        """
        # Coba login sebagai student
        response = self.client.post(
            "/api/v1/auth/sign-in",
            json={"username": "siswa01", "password": "siswa123"},
            name="POST /auth/sign-in (setup)"
        )

        if response.status_code == 200:
            self.access_token = response.json().get("access")
        else:
            # Jika login gagal, lanjutkan tanpa token (untuk test publik endpoint)
            print(f"[WARN] Login gagal: {response.status_code} — lanjut tanpa auth")

    def get_headers(self):
        """
        Kembalikan headers dengan JWT token (jika tersedia).

        Return:
            dict: Headers dengan Authorization atau empty dict
        """
        if self.access_token:
            return {"Authorization": f"Bearer {self.access_token}"}
        return {}

    # ===========================================================================
    # TASKS: Endpoint yang akan diuji
    # ===========================================================================

    @task(3)
    def get_courses_list(self):
        """
        Task paling sering: GET daftar semua course.

        Weight 3 = 30% dari semua aksi.
        Ini adalah endpoint paling umum diakses (halaman utama).
        """
        self.client.get(
            "/api/v1/courses/",
            name="GET /api/v1/courses/"
        )

    @task(2)
    def get_course_detail(self):
        """
        Task umum: GET detail satu course.

        Weight 2 = 20% dari semua aksi.
        """
        self.client.get(
            f"/api/v1/courses/{self.course_id}",
            name="GET /api/v1/courses/{id}"
        )

    @task(2)
    def get_courses_v2_paginated(self):
        """
        Task: GET daftar course via API v2 (paginated).

        Weight 2 = 20% dari semua aksi.
        Menguji endpoint v2 yang menggunakan pagination.
        """
        self.client.get(
            "/api/v2/courses/?page=1",
            name="GET /api/v2/courses/ (paginated)"
        )

    @task(1)
    def filter_courses_by_price(self):
        """
        Task: GET courses dengan filter harga.

        Weight 1 = 10% dari semua aksi.
        Menguji FilterSchema performance.
        """
        self.client.get(
            "/api/v1/courses/?min_price=100000&max_price=300000",
            name="GET /api/v1/courses/ (filtered)"
        )

    @task(1)
    def search_courses(self):
        """
        Task: GET courses dengan pencarian.

        Weight 1 = 10% dari semua aksi.
        Menguji search query performance.
        """
        self.client.get(
            "/api/v1/courses/?search=Python",
            name="GET /api/v1/courses/ (search)"
        )

    @task(1)
    def view_profile(self):
        """
        Task: GET profil user (authenticated).

        Weight 1 = 10% dari semua aksi.
        Hanya dijalankan jika user sudah login.
        """
        if not self.access_token:
            return  # Skip jika belum login

        self.client.get(
            "/api/v1/profile/",
            headers=self.get_headers(),
            name="GET /api/v1/profile/"
        )


class LMSReadHeavyUser(HttpUser):
    """
    Skenario alternatif: User yang hanya membaca (read-only).

    Cocok untuk mensimulasikan pengunjung yang belum login.
    Digunakan bersama LMSUser untuk simulasi traffic campuran.

    Aktifkan dengan: locust -f locustfile.py --class-picker
    """

    wait_time = between(2, 5)

    # Tidak perlu login
    def on_start(self):
        pass

    @task(5)
    def browse_courses(self):
        """Browse daftar course sebagai anonymous user."""
        self.client.get(
            "/api/v1/courses/",
            name="[Anon] GET /api/v1/courses/"
        )

    @task(3)
    def view_course_detail(self):
        """Lihat detail course tanpa login."""
        self.client.get(
            "/api/v1/courses/1",
            name="[Anon] GET /api/v1/courses/{id}"
        )

    @task(2)
    def browse_v2(self):
        """Browse menggunakan API v2."""
        self.client.get(
            "/api/v2/courses/?page=1",
            name="[Anon] GET /api/v2/courses/"
        )
