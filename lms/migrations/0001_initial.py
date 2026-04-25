# Generated migration for Simple LMS - all models from scratch

from django.conf import settings
import django.contrib.auth.models
import django.contrib.auth.validators
from django.db import migrations, models
import django.db.models.deletion
import django.utils.timezone


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ('auth', '0012_alter_user_first_name_max_length'),
    ]

    operations = [
        # ── 1. Custom User Model ───────────────────────────────────────────────
        migrations.CreateModel(
            name='User',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('password', models.CharField(max_length=128, verbose_name='password')),
                ('last_login', models.DateTimeField(blank=True, null=True, verbose_name='last login')),
                ('is_superuser', models.BooleanField(
                    default=False,
                    help_text='Designates that this user has all permissions without explicitly assigning them.',
                    verbose_name='superuser status'
                )),
                ('username', models.CharField(
                    error_messages={'unique': 'A user with that username already exists.'},
                    help_text='Required. 150 characters or fewer. Letters, digits and @/./+/-/_ only.',
                    max_length=150,
                    unique=True,
                    validators=[django.contrib.auth.validators.UnicodeUsernameValidator()],
                    verbose_name='username'
                )),
                ('first_name', models.CharField(blank=True, max_length=150, verbose_name='first name')),
                ('last_name', models.CharField(blank=True, max_length=150, verbose_name='last name')),
                ('email', models.EmailField(blank=True, max_length=254, verbose_name='email address')),
                ('is_staff', models.BooleanField(
                    default=False,
                    help_text='Designates whether the user can log into this admin site.',
                    verbose_name='staff status'
                )),
                ('is_active', models.BooleanField(
                    default=True,
                    help_text='Designates whether this user should be treated as active.',
                    verbose_name='active'
                )),
                ('date_joined', models.DateTimeField(default=django.utils.timezone.now, verbose_name='date joined')),
                ('role', models.CharField(
                    choices=[('admin', 'Admin'), ('instructor', 'Instructor'), ('student', 'Student')],
                    default='student',
                    max_length=20,
                    verbose_name='peran'
                )),
                ('groups', models.ManyToManyField(
                    blank=True,
                    help_text='The groups this user belongs to.',
                    related_name='user_set',
                    related_query_name='user',
                    to='auth.group',
                    verbose_name='groups'
                )),
                ('user_permissions', models.ManyToManyField(
                    blank=True,
                    help_text='Specific permissions for this user.',
                    related_name='user_set',
                    related_query_name='user',
                    to='auth.permission',
                    verbose_name='user permissions'
                )),
            ],
            options={
                'verbose_name': 'Pengguna',
                'verbose_name_plural': 'Pengguna',
            },
            managers=[
                ('objects', django.contrib.auth.models.UserManager()),
            ],
        ),

        # ── 2. Category Model (self-referencing hierarki) ─────────────────────
        migrations.CreateModel(
            name='Category',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=100, verbose_name='nama kategori')),
                ('parent', models.ForeignKey(
                    blank=True,
                    null=True,
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='subcategories',
                    to='lms.category',
                    verbose_name='induk kategori'
                )),
            ],
            options={
                'verbose_name': 'Kategori',
                'verbose_name_plural': 'Kategori',
            },
        ),

        # ── 3. Course Model ───────────────────────────────────────────────────
        migrations.CreateModel(
            name='Course',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=100, verbose_name='nama matkul')),
                ('description', models.TextField(default='-', verbose_name='deskripsi')),
                ('price', models.IntegerField(default=10000, verbose_name='harga')),
                ('image', models.ImageField(blank=True, null=True, upload_to='course_images/', verbose_name='gambar')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('instructor', models.ForeignKey(
                    limit_choices_to={'role': 'instructor'},
                    on_delete=django.db.models.deletion.RESTRICT,
                    related_name='courses_taught',
                    to=settings.AUTH_USER_MODEL,
                    verbose_name='pengajar'
                )),
                ('category', models.ForeignKey(
                    blank=True,
                    null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name='courses',
                    to='lms.category',
                    verbose_name='kategori'
                )),
            ],
            options={
                'verbose_name': 'Mata Kuliah',
                'verbose_name_plural': 'Mata Kuliah',
                'ordering': ['-created_at'],
            },
        ),

        # ── 4. Lesson Model (dengan ordering) ────────────────────────────────
        migrations.CreateModel(
            name='Lesson',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('title', models.CharField(max_length=200, verbose_name='judul materi')),
                ('content', models.TextField(verbose_name='isi materi')),
                ('video_url', models.CharField(blank=True, max_length=200, null=True, verbose_name='URL Video')),
                ('file_attachment', models.FileField(blank=True, null=True, upload_to='lesson_files/', verbose_name='File Lampiran')),
                ('order', models.PositiveIntegerField(default=0, verbose_name='urutan')),
                ('course', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='lessons',
                    to='lms.course',
                    verbose_name='matkul'
                )),
            ],
            options={
                'verbose_name': 'Materi',
                'verbose_name_plural': 'Materi',
                'ordering': ['order'],
            },
        ),

        # ── 5. Enrollment Model (dengan unique constraint) ────────────────────
        migrations.CreateModel(
            name='Enrollment',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('date_enrolled', models.DateTimeField(auto_now_add=True, verbose_name='tanggal daftar')),
                ('student', models.ForeignKey(
                    limit_choices_to={'role': 'student'},
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='enrollments',
                    to=settings.AUTH_USER_MODEL,
                    verbose_name='siswa'
                )),
                ('course', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='enrollments',
                    to='lms.course',
                    verbose_name='matkul'
                )),
            ],
            options={
                'verbose_name': 'Pendaftaran',
                'verbose_name_plural': 'Pendaftaran',
            },
        ),
        migrations.AddConstraint(
            model_name='enrollment',
            constraint=models.UniqueConstraint(
                fields=['student', 'course'],
                name='unique_student_course_enrollment'
            ),
        ),

        # ── 6. Progress Model (tracking lesson completion) ────────────────────
        migrations.CreateModel(
            name='Progress',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('is_completed', models.BooleanField(default=False, verbose_name='selesai')),
                ('completed_at', models.DateTimeField(blank=True, null=True, verbose_name='waktu selesai')),
                ('enrollment', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='progress_set',
                    to='lms.enrollment',
                    verbose_name='pendaftaran'
                )),
                ('lesson', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='progress_set',
                    to='lms.lesson',
                    verbose_name='materi'
                )),
            ],
            options={
                'verbose_name': 'Progress',
                'verbose_name_plural': 'Progress',
            },
        ),
        migrations.AddConstraint(
            model_name='progress',
            constraint=models.UniqueConstraint(
                fields=['enrollment', 'lesson'],
                name='unique_progress_per_lesson'
            ),
        ),

        # ── 7. CourseMember Model (anggota kelas - dari modul) ────────────────
        migrations.CreateModel(
            name='CourseMember',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('roles', models.CharField(
                    choices=[('std', 'Siswa'), ('ast', 'Asisten')],
                    default='std',
                    max_length=3,
                    verbose_name='peran'
                )),
                ('course_id', models.ForeignKey(
                    on_delete=django.db.models.deletion.RESTRICT,
                    to='lms.course',
                    verbose_name='matkul'
                )),
                ('user_id', models.ForeignKey(
                    on_delete=django.db.models.deletion.RESTRICT,
                    to=settings.AUTH_USER_MODEL,
                    verbose_name='pengguna'
                )),
            ],
            options={
                'verbose_name': 'Anggota Kelas',
                'verbose_name_plural': 'Anggota Kelas',
            },
        ),

        # ── 8. CourseContent Model (konten kelas - dari modul) ────────────────
        migrations.CreateModel(
            name='CourseContent',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=200, verbose_name='judul konten')),
                ('description', models.TextField(default='-', verbose_name='deskripsi')),
                ('video_url', models.CharField(blank=True, max_length=200, null=True, verbose_name='URL Video')),
                ('file_attachment', models.FileField(blank=True, null=True, upload_to='content_files/', verbose_name='File')),
                ('course_id', models.ForeignKey(
                    on_delete=django.db.models.deletion.RESTRICT,
                    to='lms.course',
                    verbose_name='matkul'
                )),
                ('parent_id', models.ForeignKey(
                    blank=True,
                    null=True,
                    on_delete=django.db.models.deletion.RESTRICT,
                    to='lms.coursecontent',
                    verbose_name='induk'
                )),
            ],
            options={
                'verbose_name': 'Konten Kelas',
                'verbose_name_plural': 'Konten Kelas',
            },
        ),

        # ── 9. Comment Model (komentar - dari modul) ──────────────────────────
        migrations.CreateModel(
            name='Comment',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('comment', models.TextField(verbose_name='komentar')),
                ('content_id', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    to='lms.coursecontent',
                    verbose_name='konten'
                )),
                ('member_id', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    to='lms.coursemember',
                    verbose_name='pengguna'
                )),
            ],
            options={
                'verbose_name': 'Komentar',
                'verbose_name_plural': 'Komentar',
            },
        ),
    ]
