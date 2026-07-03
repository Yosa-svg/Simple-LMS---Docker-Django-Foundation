# utils/validators.py
"""
Fungsi-fungsi validasi input untuk Simple LMS.

Modul 11 — Unit Testing:
Validator adalah kandidat yang bagus untuk unit testing karena:
- Input dan output terdefinisi dengan jelas
- Banyak edge case yang perlu diuji
- Tidak bergantung pada database atau service eksternal
"""

import re


def validate_password(password):
    """
    Memvalidasi kekuatan password berdasarkan 5 rules.

    Rules:
        1. Minimal 8 karakter
        2. Mengandung huruf besar (A-Z)
        3. Mengandung huruf kecil (a-z)
        4. Mengandung angka (0-9)
        5. Mengandung karakter spesial (!@#$%^&*)

    Args:
        password (str): Password yang akan divalidasi

    Returns:
        dict: {
            'is_valid' (bool): True jika semua rules terpenuhi,
            'errors'   (list): Daftar pesan error untuk rule yang dilanggar
        }

    Examples:
        >>> validate_password("SecureP@ss1")
        {'is_valid': True, 'errors': []}

        >>> validate_password("short")
        {'is_valid': False, 'errors': ['Password harus minimal 8 karakter', ...]}
    """
    errors = []

    # Rule 1: Panjang minimal 8 karakter
    if len(password) < 8:
        errors.append("Password harus minimal 8 karakter")

    # Rule 2: Mengandung huruf besar
    if not re.search(r'[A-Z]', password):
        errors.append("Password harus mengandung huruf besar")

    # Rule 3: Mengandung huruf kecil
    if not re.search(r'[a-z]', password):
        errors.append("Password harus mengandung huruf kecil")

    # Rule 4: Mengandung angka
    if not re.search(r'[0-9]', password):
        errors.append("Password harus mengandung angka")

    # Rule 5: Mengandung karakter spesial
    if not re.search(r'[!@#$%^&*]', password):
        errors.append("Password harus mengandung karakter spesial (!@#$%^&*)")

    return {
        'is_valid': len(errors) == 0,
        'errors': errors
    }
