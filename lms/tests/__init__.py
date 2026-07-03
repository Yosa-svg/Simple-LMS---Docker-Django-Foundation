# lms/tests/__init__.py
"""
Package test untuk Simple LMS — Modul 11: Automated Testing.

Struktur:
    test_calculator.py    : Unit test untuk utils.calculator
    test_validators.py    : Unit test untuk utils.validators
    test_pricing.py       : Unit test untuk utils.pricing
    test_models.py        : Unit test untuk model Django LMS
    test_api_integration.py : Integration test untuk API endpoints
    test_authorization.py : Pengujian negatif/keamanan API

Jalankan semua test:
    docker-compose exec app python manage.py test lms.tests -v 2

Jalankan dengan coverage:
    docker-compose exec app coverage run manage.py test lms.tests
    docker-compose exec app coverage report
"""
