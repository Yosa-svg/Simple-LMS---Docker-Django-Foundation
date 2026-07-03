# lms/tests/test_pricing.py
"""
Unit Test untuk utils.pricing

Modul 11 — Unit Testing + Perbandingan dengan Integration Test

Konteks:
    Unit Test ini menguji fungsi calculate_discount() SECARA TERISOLASI.
    Tidak ada database, tidak ada HTTP request, tidak ada service luar.

    Integration test untuk endpoint /api/v1/courses/{id}/ yang menampilkan
    harga course (dengan diskon) ada di test_api_integration.py.

Jalankan:
    docker-compose exec app python manage.py test lms.tests.test_pricing -v 2
"""

from django.test import TestCase
from utils.pricing import calculate_discount, apply_promo_code


class TestCalculateDiscount(TestCase):
    """
    Unit test untuk fungsi calculate_discount().

    Contoh yang digunakan di modul untuk membedakan:
    - Unit test: uji calculate_discount() langsung
    - Integration test: uji API endpoint yang menggunakan discount
    """

    def test_normal_discount(self):
        """
        Test diskon 20% dari harga 100.000.

        100.000 × 20% = 20.000 diskon
        100.000 - 20.000 = 80.000
        """
        result = calculate_discount(100000, 20)
        self.assertEqual(result, 80000)

    def test_zero_discount(self):
        """
        Test diskon 0% — harga tidak berubah.

        Edge case: diskon 0% adalah valid, bukan error.
        """
        result = calculate_discount(100000, 0)
        self.assertEqual(result, 100000)

    def test_full_discount(self):
        """
        Test diskon 100% — harga menjadi nol.

        Edge case: diskon 100% valid (gratis total).
        """
        result = calculate_discount(100000, 100)
        self.assertEqual(result, 0)

    def test_discount_50_percent(self):
        """Test diskon tepat 50%."""
        result = calculate_discount(200000, 50)
        self.assertEqual(result, 100000)

    def test_invalid_discount_negative_raises_error(self):
        """
        Test diskon negatif — harus raise ValueError.

        Diskon negatif tidak masuk akal secara bisnis.
        """
        with self.assertRaises(ValueError) as context:
            calculate_discount(100000, -10)
        self.assertIn("Discount harus antara 0 dan 100", str(context.exception))

    def test_invalid_discount_over_100_raises_error(self):
        """
        Test diskon lebih dari 100% — harus raise ValueError.

        Diskon > 100% tidak masuk akal (harga jadi negatif).
        """
        with self.assertRaises(ValueError):
            calculate_discount(100000, 150)

    def test_discount_with_float_percentage(self):
        """Test diskon dengan persentase desimal (10.5%)."""
        result = calculate_discount(100000, 10.5)
        self.assertEqual(result, 89500)


class TestApplyPromoCode(TestCase):
    """Test cases untuk fungsi apply_promo_code()."""

    def test_valid_promo_code_student10(self):
        """Test kode promo STUDENT10 memberikan diskon 10%."""
        result = apply_promo_code(100000, 'STUDENT10')
        self.assertTrue(result['valid'])
        self.assertEqual(result['final_price'], 90000)
        self.assertEqual(result['discount'], 10000)

    def test_valid_promo_code_case_insensitive(self):
        """Test kode promo tidak case-sensitive."""
        result = apply_promo_code(100000, 'student10')
        self.assertTrue(result['valid'])
        self.assertEqual(result['final_price'], 90000)

    def test_invalid_promo_code(self):
        """Test kode promo tidak valid — harga tidak berubah."""
        result = apply_promo_code(100000, 'INVALID')
        self.assertFalse(result['valid'])
        self.assertEqual(result['final_price'], 100000)
        self.assertEqual(result['discount'], 0)

    def test_promo_newuser50_gives_half_price(self):
        """Test kode NEWUSER50 memberikan diskon 50%."""
        result = apply_promo_code(200000, 'NEWUSER50')
        self.assertTrue(result['valid'])
        self.assertEqual(result['final_price'], 100000)
