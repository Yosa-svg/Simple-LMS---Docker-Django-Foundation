# Simple-LMS---Docker-Django-Foundation

**Nama:** [Yosafat Goradipa B]  
**NIM:** [15079]

---

## Deskripsi Proyek

Proyek ini adalah inisialisasi awal (_setup environment_) untuk pengembangan sistem informasi **Simple LMS**. Proyek ini menggunakan **Django** sebagai _backend framework_ dan **PostgreSQL** sebagai sistem basis data relasional. Seluruh infrastruktur dibungkus ke dalam _container_ menggunakan **Docker** dan **Docker Compose** dengan mematuhi standar _best practices_.

---

## Struktur Proyek (Best Practice)

Sesuai standar pemisahan konfigurasi, proyek ini menggunakan struktur:

- `config/`: Folder utama berisi konfigurasi Django (`settings.py`, `urls.py`).
- `manage.py`: Script eksekusi utama Django.
- `Dockerfile` & `docker-compose.yml`: Orkestrasi _container_ web dan _database_.
- `requirements.txt`: Daftar pustaka (Django & Psycopg2).
- `.env.example`: _Template_ penyimpanan kredensial rahasia.

---

## Cara Menjalankan Proyek

1. **Persiapan:** Pastikan **Docker** sudah berjalan di sistem Anda.
2. **Kloning/Download Proyek:** Buka terminal dan arahkan ke dalam direktori proyek.
3. **Setup Environment:** Duplikat file `.env.example` dan ubah namanya menjadi `.env`.
4. **Build & Run:** Eksekusi perintah berikut untuk membangun _image_ dan menjalankan _container_ di latar belakang:
   ```bash
   docker compose up -d --build
   ```
<img width="956" height="446" alt="image" src="https://github.com/user-attachments/assets/46b7eae3-be72-4e4c-90b4-1bc6d79d8904" />
