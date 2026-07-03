# utils/pricing.py
"""
Fungsi-fungsi kalkulasi harga untuk Simple LMS.

Modul 11 — Unit Testing:
Digunakan sebagai contoh perbedaan unit test vs integration test.
- Unit test: menguji calculate_discount() secara terisolasi
- Integration test: menguji endpoint API yang MENGGUNAKAN calculate_discount()
"""


def calculate_discount(price, discount_percentage):
    """
    Menghitung harga setelah diskon.

    Args:
        price (int|float): Harga asli (harus bilangan positif)
        discount_percentage (int|float): Persentase diskon (0-100)

    Returns:
        float: Harga setelah diskon diterapkan

    Raises:
        ValueError: Jika discount_percentage di luar range 0-100

    Examples:
        >>> calculate_discount(100000, 20)
        80000.0

        >>> calculate_discount(100000, 0)
        100000.0

        >>> calculate_discount(100000, 100)
        0.0
    """
    if discount_percentage < 0 or discount_percentage > 100:
        raise ValueError("Discount harus antara 0 dan 100")

    discount_amount = price * (discount_percentage / 100)
    return price - discount_amount


def apply_promo_code(price, promo_code):
    """
    Menerapkan kode promo ke harga.

    Kode promo yang tersedia:
    - 'STUDENT10' → diskon 10%
    - 'EARLYBIRD' → diskon 25%
    - 'NEWUSER50' → diskon 50%

    Args:
        price (int|float): Harga asli
        promo_code (str): Kode promo

    Returns:
        dict: {'final_price': float, 'discount': float, 'valid': bool}
    """
    promo_codes = {
        'STUDENT10': 10,
        'EARLYBIRD': 25,
        'NEWUSER50': 50,
    }

    code = promo_code.upper().strip()
    if code not in promo_codes:
        return {
            'final_price': price,
            'discount': 0,
            'valid': False,
        }

    discount_pct = promo_codes[code]
    final_price = calculate_discount(price, discount_pct)
    return {
        'final_price': final_price,
        'discount': price - final_price,
        'valid': True,
    }
