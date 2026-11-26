from concurrent.futures import ThreadPoolExecutor
from datetime import date

from app.core.exceptions import AppError
from app.services import journals


def test_concurrent_old_cloud_writes_are_all_rejected_without_database_access():
    def attempt(_):
        try:
            journals.save(None, None, date(2026, 11, 5), None)
        except AppError as error:
            return error.status_code
        raise AssertionError("Old cloud write unexpectedly succeeded")

    with ThreadPoolExecutor(max_workers=2) as workers:
        assert list(workers.map(attempt, range(8))) == [403] * 8
