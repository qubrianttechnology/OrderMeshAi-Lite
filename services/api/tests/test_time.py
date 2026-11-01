from datetime import datetime, timedelta, timezone

from app.models import as_utc


def test_database_timezone_is_converted_not_relabelled():
    colombo = datetime(
        2026, 10, 23, 5, 30, tzinfo=timezone(timedelta(hours=5, minutes=30))
    )
    utc = datetime(2026, 10, 23, 0, 0, tzinfo=timezone.utc)
    assert as_utc(colombo) == utc
    assert as_utc(utc.replace(tzinfo=None)) == utc
