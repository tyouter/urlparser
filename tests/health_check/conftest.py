import pytest


class _HealthReport:
    def __init__(self):
        self.results = []
        self.start_time = 0
        self.report_path = None

    def add(self, r):
        self.results.append(r)

    def add_batch(self, category, results):
        for r in results:
            if hasattr(r, 'category'):
                r.category = category
            self.results.append(r)


@pytest.fixture
def report():
    return _HealthReport()
