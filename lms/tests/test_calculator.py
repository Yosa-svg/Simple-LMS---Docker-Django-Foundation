# lms/tests/test_calculator.py
"""
Unit Test untuk utils.calculator

Modul 11 — Unit Testing (Studi Kasus 1)

Pola setiap test: Arrange → Act → Assert
- Arrange: Tidak ada setup (fungsi murni tidak butuh state)
- Act    : Panggil fungsi yang diuji
- Assert : Verifikasi hasil dengan assertEqual, assertRaises, dsb.

Jalankan:
    docker-compose exec app python manage.py test lms.tests.test_calculator -v 2
"""

from django.test import TestCase
from utils.calculator import add, subtract, multiply, divide


class TestAdd(TestCase):
    """Test cases untuk fungsi add()."""

    def test_add_positive_numbers(self):
        """Test penjumlahan dua bilangan positif."""
        # Arrange: tidak perlu — fungsi murni
        # Act
        result = add(2, 3)
        # Assert
        self.assertEqual(result, 5)

    def test_add_negative_numbers(self):
        """Test penjumlahan dua bilangan negatif."""
        result = add(-1, -1)
        self.assertEqual(result, -2)

    def test_add_mixed_numbers(self):
        """Test penjumlahan bilangan positif dan negatif — hasil nol."""
        result = add(-1, 1)
        self.assertEqual(result, 0)

    def test_add_with_zero(self):
        """Test penjumlahan dengan nol — identitas penjumlahan."""
        self.assertEqual(add(5, 0), 5)
        self.assertEqual(add(0, 5), 5)


class TestSubtract(TestCase):
    """Test cases untuk fungsi subtract()."""

    def test_subtract_positive_numbers(self):
        """Test pengurangan dengan hasil positif."""
        result = subtract(5, 3)
        self.assertEqual(result, 2)

    def test_subtract_negative_result(self):
        """Test pengurangan dengan hasil negatif."""
        result = subtract(3, 5)
        self.assertEqual(result, -2)

    def test_subtract_same_numbers(self):
        """Test pengurangan bilangan sama — hasil nol."""
        result = subtract(7, 7)
        self.assertEqual(result, 0)


class TestMultiply(TestCase):
    """Test cases untuk fungsi multiply()."""

    def test_multiply_positive_numbers(self):
        """Test perkalian dua bilangan positif."""
        result = multiply(3, 4)
        self.assertEqual(result, 12)

    def test_multiply_by_zero(self):
        """Test perkalian dengan nol — hasilnya selalu nol."""
        self.assertEqual(multiply(5, 0), 0)
        self.assertEqual(multiply(0, 999), 0)

    def test_multiply_negative_numbers(self):
        """Test perkalian dua bilangan negatif — hasil positif."""
        result = multiply(-3, -4)
        self.assertEqual(result, 12)


class TestDivide(TestCase):
    """Test cases untuk fungsi divide()."""

    def test_divide_positive_numbers(self):
        """Test pembagian bilangan positif — hasil genap."""
        result = divide(10, 2)
        self.assertEqual(result, 5)

    def test_divide_returns_float(self):
        """Test pembagian menghasilkan float jika tidak genap."""
        result = divide(7, 2)
        self.assertEqual(result, 3.5)

    def test_divide_by_zero_raises_error(self):
        """
        Test pembagian dengan nol HARUS melempar ValueError.

        Menggunakan assertRaises sebagai context manager:
        - Blok 'with' menjalankan kode
        - Jika ValueError dilempar → test PASS
        - Jika tidak ada exception → test FAIL
        """
        with self.assertRaises(ValueError) as context:
            divide(10, 0)
        # Verifikasi pesan error yang benar
        self.assertEqual(
            str(context.exception),
            "Tidak bisa membagi dengan nol!"
        )

    def test_divide_negative_numbers(self):
        """Test pembagian bilangan negatif."""
        result = divide(-10, 2)
        self.assertEqual(result, -5)
