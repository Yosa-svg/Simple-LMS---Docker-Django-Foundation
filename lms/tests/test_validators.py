# lms/tests/test_validators.py
"""
Unit Test untuk utils.validators

Modul 11 — Unit Testing (Studi Kasus 2)

Validator adalah contoh ideal untuk unit testing:
- Input dan output terdefinisi jelas (dict dengan is_valid + errors)
- Banyak edge case (password kosong, terlalu pendek, missing char types)
- Pure function — tidak ada dependensi database/network

Jalankan:
    docker-compose exec app python manage.py test lms.tests.test_validators -v 2
"""

from django.test import TestCase
from utils.validators import validate_password


class TestPasswordValidator(TestCase):
    """
    Test cases untuk fungsi validate_password.

    Setiap test memverifikasi satu skenario spesifik.
    Best practice: nama test = apa yang diuji + apa yang diharapkan.
    """

    def test_valid_password_passes_all_rules(self):
        """
        Test password yang memenuhi semua 5 kriteria.

        Happy path: skenario sukses yang harus selalu berhasil.
        'SecureP@ss1' memiliki:
        - Panjang > 8 ✓
        - Huruf besar (S, P) ✓
        - Huruf kecil (ecure, ss) ✓
        - Angka (1) ✓
        - Karakter spesial (@) ✓
        """
        result = validate_password("SecureP@ss1")
        self.assertTrue(result['is_valid'])
        self.assertEqual(len(result['errors']), 0)

    def test_password_too_short_fails(self):
        """
        Test password yang terlalu pendek (< 8 karakter).

        'Ab1!' hanya 4 karakter — harus mengandung error panjang.
        """
        result = validate_password("Ab1!")
        self.assertFalse(result['is_valid'])
        self.assertIn("Password harus minimal 8 karakter", result['errors'])

    def test_password_no_uppercase_fails(self):
        """
        Test password tanpa huruf besar.

        'password1!' memiliki lowercase, angka, spesial, panjang cukup,
        tapi tidak ada uppercase — harus fail.
        """
        result = validate_password("password1!")
        self.assertFalse(result['is_valid'])
        self.assertIn("Password harus mengandung huruf besar", result['errors'])

    def test_password_no_lowercase_fails(self):
        """
        Test password tanpa huruf kecil.

        'PASSWORD1!' semuanya uppercase — harus fail.
        """
        result = validate_password("PASSWORD1!")
        self.assertFalse(result['is_valid'])
        self.assertIn("Password harus mengandung huruf kecil", result['errors'])

    def test_password_no_number_fails(self):
        """
        Test password tanpa angka.

        'Password!' ada uppercase, lowercase, spesial, panjang OK,
        tapi tidak ada angka.
        """
        result = validate_password("Password!")
        self.assertFalse(result['is_valid'])
        self.assertIn("Password harus mengandung angka", result['errors'])

    def test_password_no_special_char_fails(self):
        """
        Test password tanpa karakter spesial.

        'Password1' ada segalanya kecuali karakter spesial.
        """
        result = validate_password("Password1")
        self.assertFalse(result['is_valid'])
        self.assertIn(
            "Password harus mengandung karakter spesial (!@#$%^&*)",
            result['errors']
        )

    def test_password_with_multiple_errors(self):
        """
        Test password dengan banyak kesalahan sekaligus.

        'abc' melanggar: panjang, huruf besar, angka, karakter spesial
        → minimal 4 error.
        """
        result = validate_password("abc")
        self.assertFalse(result['is_valid'])
        # Minimal 4 error (panjang, uppercase, angka, spesial)
        self.assertGreaterEqual(len(result['errors']), 4)

    def test_empty_password_fails(self):
        """
        Test edge case: password kosong.

        String kosong melanggar semua 5 rules → 5 error.
        """
        result = validate_password("")
        self.assertFalse(result['is_valid'])
        self.assertEqual(len(result['errors']), 5)

    def test_password_returns_dict_structure(self):
        """
        Test bahwa fungsi selalu mengembalikan struktur dict yang benar.

        Verifikasi bahwa output selalu memiliki key 'is_valid' dan 'errors'.
        """
        result = validate_password("AnyPass123!")
        self.assertIn('is_valid', result)
        self.assertIn('errors', result)
        self.assertIsInstance(result['is_valid'], bool)
        self.assertIsInstance(result['errors'], list)

    def test_all_special_chars_accepted(self):
        """
        Test bahwa semua karakter spesial yang diizinkan berfungsi.

        Validator mendukung: !@#$%^&*
        """
        special_chars = ['!', '@', '#', '$', '%', '^', '&', '*']
        for char in special_chars:
            password = f"Password1{char}"
            result = validate_password(password)
            self.assertTrue(
                result['is_valid'],
                msg=f"Password dengan '{char}' seharusnya valid, tapi: {result['errors']}"
            )
