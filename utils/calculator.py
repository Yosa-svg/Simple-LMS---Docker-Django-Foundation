# utils/calculator.py
"""
Fungsi-fungsi kalkulator sederhana.

Modul 11 — Unit Testing:
Fungsi-fungsi ini sengaja dibuat sederhana sebagai contoh
unit testing yang mudah dipahami.

Karakteristik yang baik untuk unit test:
- Fungsi murni (pure function): output hanya bergantung pada input
- Tidak ada side effects (tidak ubah state luar)
- Deterministik: input sama → output selalu sama
"""


def add(a, b):
    """
    Menjumlahkan dua bilangan.

    Args:
        a: Bilangan pertama
        b: Bilangan kedua

    Returns:
        Hasil penjumlahan a + b

    Examples:
        >>> add(2, 3)
        5
        >>> add(-1, 1)
        0
    """
    return a + b


def subtract(a, b):
    """
    Mengurangkan bilangan b dari a.

    Args:
        a: Bilangan yang dikurangi (minuend)
        b: Bilangan pengurang (subtrahend)

    Returns:
        Hasil pengurangan a - b

    Examples:
        >>> subtract(5, 3)
        2
        >>> subtract(3, 5)
        -2
    """
    return a - b


def multiply(a, b):
    """
    Mengalikan dua bilangan.

    Args:
        a: Faktor pertama
        b: Faktor kedua

    Returns:
        Hasil perkalian a × b

    Examples:
        >>> multiply(3, 4)
        12
        >>> multiply(5, 0)
        0
    """
    return a * b


def divide(a, b):
    """
    Membagi bilangan a dengan b.

    Args:
        a: Bilangan yang dibagi (dividend)
        b: Pembagi (divisor) — tidak boleh nol

    Returns:
        Hasil pembagian a / b (float)

    Raises:
        ValueError: Jika b adalah 0

    Examples:
        >>> divide(10, 2)
        5.0
        >>> divide(7, 2)
        3.5
    """
    if b == 0:
        raise ValueError("Tidak bisa membagi dengan nol!")
    return a / b
