"""Simple unit tests for ml_tasks functions (mainly run_stats).

These aren't wired into a test framework in the MVP, so they can be run
manually via `python -m worker.test_ml_tasks` or similar.  They help
catch the CSV-related bug described in the issue.
"""

from worker.ml_tasks import run_stats


def _assert_no_error(payload):
    try:
        result = run_stats(payload)
    except Exception as e:
        raise AssertionError(f"run_stats raised {e} for payload {payload}")
    return result


def test_basic():
    data = ["hello world", "foo bar"]
    res = run_stats({"data": data, "config": {"job_type": "stats"}})
    assert "stats" in res


def test_structured():
    data = [{"a": "one", "b": "two"}, {"a": "three"}]
    res = run_stats({"data": data, "config": {"job_type": "stats"}})
    assert res["stats"]["total_texts"] == 2


def test_mixed_types():
    # row contains numbers and nested dicts
    data = [{"a": 1, "b": {"x": 2}}, {"c": None}]
    res = run_stats({"data": data, "config": {"job_type": "stats"}})
    assert res["stats"]["total_texts"] == 2


def test_csv_like():
    rows = [
        {"col1": "hello", "col2": "world"},
        {"col1": "foo", "col2": "bar"},
    ]
    res = run_stats({"data": rows, "config": {"job_type": "stats"}})
    assert res["stats"]["total_texts"] == 2


def main():
    test_basic()
    test_structured()
    test_mixed_types()
    test_csv_like()
    print("all tests passed")


if __name__ == "__main__":
    main()
