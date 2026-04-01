FROM python:3.10-slim

# Mencegah Python menulis file .pyc ke disk
ENV PYTHONDONTWRITEBYTECODE 1
# Memastikan output Python langsung dikirim ke terminal (untuk debugging)
ENV PYTHONUNBUFFERED 1

# Menentukan folder kerja di dalam container
WORKDIR /app

# Menginstal dependencies
COPY requirements.txt /app/
RUN pip install --upgrade pip && pip install -r requirements.txt

# Menyalin seluruh file proyek ke dalam container
COPY . /app/