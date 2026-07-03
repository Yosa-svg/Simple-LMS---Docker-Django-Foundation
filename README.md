# 🎓 Simple LMS — Backend API

> **Final Project** · Mata Kuliah Pemrograman Berbasis Komponen
>
> **Nama:** Yosafat Goradipa B · **NIM:** 15079

Backend lengkap _Learning Management System_ yang dibangun dengan **Django + Django Ninja**, mengintegrasikan **PostgreSQL**, **Redis**, **MongoDB**, **RabbitMQ**, dan **Celery** dalam arsitektur _polyglot persistence_ yang di-containerize menggunakan **Docker Compose**.

---

##  Arsitektur Sistem

```
┌─────────────────────────────────────────────────────────────────┐
│                        CLIENT (Browser/Postman)                 │
└─────────────────────────┬───────────────────────────────────────┘
                          │ HTTP :8000
┌─────────────────────────▼───────────────────────────────────────┐
│              Django + Django Ninja  (REST API + JWT)            │
└──────┬─────────────┬──────────────┬───────────────┬────────────┘
       │ ORM         │ Cache        │ Log Activity  │ Async Task
┌──────▼──────┐ ┌────▼────┐ ┌──────▼─────┐ ┌──────▼───────────┐
│ PostgreSQL  │ │  Redis  │ │  MongoDB   │ │    RabbitMQ      │
│ (Data Utama)│ │(Cache & │ │(Analytics &│ │ (Message Broker) │
│ Port 5432   │ │ Session)│ │   Logs)    │ │   Port 5672      │
│             │ │Port 6379│ │Port 27017  │ └──────┬───────────┘
└─────────────┘ └─────────┘ └────────────┘        │ Consume
                                           ┌───────▼────────────┐
                                           │  Celery Worker     │
                                           │  Celery Beat       │
                                           │  Flower :5555      │
                                           └────────────────────┘
```

### Komponen & Perannya

| Komponen | Teknologi | Peran |
|---|---|---|
| REST API | Django 4.x + Django Ninja | Endpoint CRUD, JWT Auth, Business Logic |
| Database Utama | PostgreSQL 15 | Users, Courses, Enrollments, Comments |
| Cache & Session | Redis 7 | Cache response API (TTL), Session, Rate Limiting |
| Analytics Store | MongoDB 7 | Activity Logs, Aggregation Analytics |
| Message Broker | RabbitMQ 3 | Antrian pesan untuk Celery workers |
| Async Tasks | Celery Worker | Email notifikasi, Report generation |
| Periodic Tasks | Celery Beat | Daily stats, Cache cleanup |
| Task Monitor | Flower | Dashboard monitoring Celery tasks |

---

##  Cara Menjalankan Proyek

### Prasyarat
- **Docker Desktop** terinstall dan berjalan
- **Git** untuk clone repository

### 1. Clone Repository
```bash
git clone <repository-url>
cd simple-lms
```

### 2. Setup Environment Variables
```bash
cp .env.example .env
# Edit .env jika perlu menyesuaikan credentials
```

### 3. Jalankan Semua Services
```bash
docker-compose up -d --build
```

Tunggu semua service siap (~30-60 detik), lalu verifikasi:
```bash
docker-compose ps
```

### 4. Generate RSA Keys (untuk JWT)
```bash
docker-compose exec app python manage.py make_rsa
```

### 5. Seed Data (Opsional)
```bash
# Data PostgreSQL (users, courses, enrollments)
docker-compose exec app python generate_data.py

# Data MongoDB (500 activity logs untuk analytics)
docker-compose exec app python lms/seed_mongo.py
```

### Fresh Reset (hapus semua data)
```bash
docker-compose down -v
docker-compose up -d --build
```

---

##  Service URLs

| Service | URL | Credentials |
|---|---|---|
| **Django API** | http://localhost:8000/api/v1/ | — |
| **Swagger UI (API Docs)** | http://localhost:8000/api/v1/docs | — |
| **Django Admin** | http://localhost:8000/admin/ | `admin` / `admin123` |
| **RabbitMQ Management** | http://localhost:15672 | `guest` / `guest` |
| **Flower (Celery Monitor)** | http://localhost:5555 | — |

---

##  Dokumentasi API

Dokumentasi interaktif tersedia di **http://localhost:8000/api/v1/docs** (Swagger UI).

### Authentication
```bash
# 1. Register
POST /api/v1/register
{ "username": "john", "email": "john@example.com", "password": "secret123" }

# 2. Login → dapat access_token
POST /api/v1/auth/sign-in
{ "username": "john", "password": "secret123" }

# 3. Gunakan token di header
Authorization: Bearer <access_token>
```

### Endpoint Utama

####  User Management
| Method | Endpoint | Deskripsi |
|---|---|---|
| POST | `/api/v1/register` | Registrasi user baru |
| POST | `/api/v1/auth/sign-in` | Login, dapat JWT token |
| POST | `/api/v1/auth/token-refresh` | Refresh access token |

####  Course Management
| Method | Endpoint | Auth | Deskripsi |
|---|---|---|---|
| GET | `/api/v1/courses/` | Tidak | List semua course (filter, sort, pagination) |
| GET | `/api/v1/courses/{id}/` | Tidak | Detail course |
| POST | `/api/v1/courses/` | Ya | Buat course baru |
| PUT | `/api/v1/courses/{id}/` | Ya (Owner) | Update course |
| PATCH | `/api/v1/courses/{id}/` | Ya (Owner) | Partial update |
| DELETE | `/api/v1/courses/{id}/` | Ya (Owner/Admin) | Hapus course |

**Query Params untuk GET `/courses/`:**
- `?search=django` — filter by nama
- `?ordering=price` — sort by price/name/date
- `?page=1&page_size=10` — pagination
- `?min_price=50000&max_price=500000` — filter harga

####  Content Management
| Method | Endpoint | Auth | Deskripsi |
|---|---|---|---|
| GET | `/api/v1/courses/{id}/contents/` | Ya (Enrolled) | List materi course |
| POST | `/api/v1/contents/` | Ya (Owner) | Tambah materi baru |
| PUT | `/api/v1/contents/{id}/` | Ya (Owner) | Update materi |
| DELETE | `/api/v1/contents/{id}/` | Ya (Owner) | Hapus materi |
| POST | `/api/v1/contents/{id}/upload-attachment/` | Ya (Owner) | Upload file |
| GET | `/api/v1/contents/{id}/download/` | Ya (Enrolled) | Download attachment |

####  Enrollment
| Method | Endpoint | Auth | Deskripsi |
|---|---|---|---|
| POST | `/api/v1/courses/{id}/enroll/` | Ya | Daftar ke course (async email) |
| GET | `/api/v1/mycourses/` | Ya | Course yang diikuti user |

####  Comments
| Method | Endpoint | Auth | Deskripsi |
|---|---|---|---|
| POST | `/api/v1/comments/` | Ya (Enrolled) | Posting komentar |
| PUT | `/api/v1/comments/{id}/` | Ya (Owner) | Edit komentar |
| DELETE | `/api/v1/comments/{id}/` | Ya (Owner/Instructor) | Hapus komentar |

####  Analytics (MongoDB)
| Method | Endpoint | Auth | Deskripsi |
|---|---|---|---|
| GET | `/api/v1/analytics/popular-courses/` | Ya | Top course by views (aggregation) |
| GET | `/api/v1/analytics/my-activity/` | Ya | Riwayat aktivitas user |
| GET | `/api/v1/analytics/daily-summary/` | Ya | Statistik harian (N hari) |
| POST | `/api/v1/analytics/log/` | Ya | Catat aktivitas manual |
| GET | `/api/v1/analytics/enrollment-stats/` | Ya | Statistik enrollment |

####  Async Tasks (Celery)
| Method | Endpoint | Auth | Deskripsi |
|---|---|---|---|
| POST | `/api/v1/courses/{id}/export-report/` | Ya (Owner) | Generate CSV report (async) |
| POST | `/api/v1/reports/generate/{id}/` | Ya (Owner) | Generate JSON report (async) |
| GET | `/api/v1/reports/status/{task_id}/` | Ya | Cek status task |

####  Redis — Popular & History (Sorted Set)
| Method | Endpoint | Auth | Deskripsi |
|---|---|---|---|
| GET | `/api/v1/courses/popular/` | Tidak | Top course by Redis Sorted Set |
| POST | `/api/v1/courses/{id}/visit/` | Ya | Increment popularity counter |
| GET | `/api/v1/courses/my-history/` | Ya | Riwayat course yang dikunjungi |

---

##  Teknologi & Versi

```
Django             4.x
Django Ninja       1.x
django-ninja-simple-jwt  (JWT Auth)
django-redis       (Redis Cache Backend)
celery             5.x
flower             2.x
pymongo            4.x
django-celery-beat
django-celery-results
gunicorn           (Production WSGI)
```

---

##  Struktur Database

### PostgreSQL (Data Utama)
```
users           — User accounts (Django built-in)
lms_course      — Daftar course
lms_coursemember— Enrollment (user ↔ course, role: teacher/student)
lms_coursecontent— Materi/lesson
lms_comment     — Komentar pada materi
```

### Redis (Cache)
```
DB 0: Application Cache (course list, course detail)
      Key pattern: course:list:*, course:detail:{id}
      Session storage
      Rate limiting counter
      Sorted Set: course popularity leaderboard
DB 1: Celery Result Backend
```

### MongoDB (Analytics)
```
Database: simple_lms_logs
Collection: activity_logs
  {
    user_id, username, action, resource,
    timestamp, ip_address,
    metadata: { course_id, course_name, browser, ... }
  }
Indexes: user_id+timestamp, action, course_id+action
```

---

##  Menjalankan Tests

```bash
# Jalankan semua tests dengan coverage report
docker-compose exec app python -m pytest lms/tests/ --cov=lms --cov-config=.coveragerc -q

# Dengan laporan baris yang tidak ter-cover (term-missing)
docker-compose exec app python -m pytest lms/tests/ --cov=lms --cov-report=term-missing -q

# Hanya unit tests model
docker-compose exec app python -m pytest lms/tests/test_models.py -v

# Hanya integration tests API
docker-compose exec app python -m pytest lms/tests/test_api_integration.py -v

# Hanya authorization tests
docker-compose exec app python -m pytest lms/tests/test_authorization.py -v

# Test spesifik
docker-compose exec app python -m pytest lms/tests/test_api_integration.py::TestCourseAPI -v
```

### Hasil Coverage (Aktual)

| Modul | Coverage |
|---|---|
| `lms/admin.py` | **100%** |
| `lms/schemas.py` | **99%** |
| `lms/models.py` | **92%** |
| `lms/helpers.py` | **91%** |
| `lms/middleware.py` | **80%** |
| `lms/apiv2.py` | **78%** |
| `lms/apiv1.py` | **63%** |
| **TOTAL** | **77%+**  |

- Threshold minimum: **70%** (`.coveragerc` `fail_under`)
- Total test: **124 passed, 0 failed**

---

## Performa

Hasil benchmark (`python benchmark.py`):

| Endpoint | Avg Response | P95 |
|---|---|---|
| GET /courses/ (cached) | ~55 ms | ~91 ms |
| GET /courses/?search=... (uncached) | ~58 ms | ~88 ms |
| GET /courses/popular/ (Redis Sorted Set) | ~70 ms | ~110 ms |

*Tested: 100 requests per endpoint, localhost*

---

##  Docker Services

```yaml
# Semua services didefinisikan di docker-compose.yml
app          → Django API (port 8000)
db           → PostgreSQL 15 (port 5432)
redis        → Redis 7 (port 6379)
mongodb      → MongoDB 7 (port 27017)
rabbitmq     → RabbitMQ 3 (port 5672, 15672)
celery-worker→ Celery Worker
celery-beat  → Celery Beat (Periodic Tasks)
flower       → Flower Dashboard (port 5555)
```

### Useful Commands
```bash
# Cek log service tertentu
docker-compose logs -f app
docker-compose logs -f celery-worker

# Masuk ke shell Django
docker-compose exec app python manage.py shell

# Masuk ke MongoDB shell
docker-compose exec mongodb mongosh

# Cek status semua service
docker-compose ps
```

---

##  Fitur yang Diimplementasikan

###  Checklist Final Project

- [x] Docker Compose dengan semua services (app, db, redis, mongodb, rabbitmq, celery, flower)
- [x] REST API CRUD: Courses, Contents, Comments, Enrollments
- [x] JWT Authentication (register, login, token refresh)
- [x] Authorization: owner-only, enrolled-only, admin-only
- [x] Filtering, Sorting, Pagination pada GET /courses/
- [x] File upload (course thumbnail, content attachment)
- [x] Redis Caching pada GET /courses/ dan GET /courses/{id}/
- [x] Cache invalidation saat create/update/delete
- [x] Session management via Redis
- [x] Rate Limiting (20 req/min anon, 100 req/min auth)
- [x] MongoDB Activity Logging (view, enroll, comment)
- [x] MongoDB Aggregation Analytics (popular courses, daily stats)
- [x] Celery async email notifikasi saat enrollment
- [x] Celery async report generation (CSV + JSON)
- [x] Celery Beat periodic tasks (daily stats, cleanup)
- [x] API Documentation (Swagger UI di /api/v1/docs)
- [x] Automated Tests (pytest + coverage)
- [x] Redis Sorted Set untuk popularity leaderboard

---

##  Security Notes

- `.env` file **tidak di-commit** ke repository (lihat `.gitignore`)
- JWT menggunakan RSA key pair (`jwt-signing.pem` / `.pub`) — tidak di-commit
- Gunakan `.env.example` sebagai template, ganti nilai sebelum production
- Untuk production: set `DEBUG=False`, ganti semua passwords

---

##  Kontribusi

```
Yosafat Goradipa B (15079)
  - Implementasi seluruh sistem dari Modul 01-13
  - Setup Docker Compose multi-service architecture
  - Implementasi REST API dengan Django Ninja
  - Integrasi Redis, MongoDB, Celery, RabbitMQ
  - Automated testing dengan pytest
```
