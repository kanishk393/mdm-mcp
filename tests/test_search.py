from __future__ import annotations

import pytest

from mdm_mcp.search.engine import FilterError
from mdm_mcp.services.dataset_service import DatasetService
from mdm_mcp.services.row_service import RowService

COLUMNS = [
    {"name": "name", "type": "string"},
    {"name": "stage", "type": "enum", "options": ["Applied", "Screened", "Rejected"]},
    {"name": "score", "type": "float"},
    {"name": "applied_on", "type": "date"},
]


def make_services(repo):
    return DatasetService(repo), RowService(repo)


def seed(repo, count_by_stage):
    svc, rows = make_services(repo)
    svc.create_dataset("Candidates", "", COLUMNS)
    batch = []
    day = 1
    for stage, count in count_by_stage.items():
        for i in range(count):
            batch.append({
                "name": f"Candidate {stage} {i}",
                "stage": stage,
                "score": (i % 10) + 1,
                "applied_on": f"2026-08-{day:02d}",
            })
            day += 1
    rows.add_rows("Candidates", batch)
    return svc, rows


def test_equality_filter_reports_total(repo):
    svc, rows = seed(repo, {"Applied": 4, "Rejected": 6})
    result = rows.search_rows("Candidates", conditions=[{"column": "stage", "op": "eq", "value": "Applied"}])
    assert result["total"] == 4 and result["count"] == 4
    assert all(r["stage"] == "Applied" for r in result["rows"])


def test_unknown_column_error(repo):
    svc, rows = seed(repo, {"Applied": 1})
    with pytest.raises(FilterError, match="not defined"):
        rows.search_rows("Candidates", conditions=[{"column": "emial", "op": "eq", "value": "x"}])


def test_date_between_filter(repo):
    svc, rows = seed(repo, {"Applied": 3})
    result = rows.search_rows("Candidates", conditions=[{"column": "applied_on", "op": "between", "value": ["2026-08-01", "2026-08-02"]}])
    assert result["total"] == 2


def test_sort_desc_and_pagination(repo):
    svc, rows = seed(repo, {"Applied": 25})
    page1 = rows.search_rows("Candidates", sort_by="applied_on", sort_order="desc", limit=20)
    assert page1["total"] == 25 and page1["count"] == 20 and page1["next_offset"] == 20
    assert page1["rows"][0]["applied_on"] == "2026-08-25"
    page2 = rows.search_rows("Candidates", sort_by="applied_on", sort_order="desc", limit=20, offset=20)
    assert page2["count"] == 5 and page2["next_offset"] is None
    assert page2["rows"][-1]["applied_on"] == "2026-08-01"


def test_sort_unknown_column(repo):
    svc, rows = seed(repo, {"Applied": 1})
    with pytest.raises(FilterError, match="not a column"):
        rows.search_rows("Candidates", sort_by="emial")


def test_sort_none_values_last(repo):
    svc, rows = make_services(repo)
    svc.create_dataset("Candidates", "", COLUMNS)
    rows.add_rows("Candidates", [{"name": "A"}, {"name": "B", "score": 5}])
    result = rows.search_rows("Candidates", sort_by="score")
    assert [r["score"] for r in result["rows"]] == [5.0, None]


def test_projection(repo):
    svc, rows = seed(repo, {"Applied": 2})
    result = rows.search_rows("Candidates", columns=["name", "stage"])
    assert set(result["rows"][0]) == {"id", "name", "stage"}


def test_limit_clamped(repo):
    svc, rows = seed(repo, {"Applied": 3})
    result = rows.search_rows("Candidates", limit=500)
    assert result["count"] == 3


def test_search_all_rows_without_conditions(repo):
    svc, rows = seed(repo, {"Applied": 2, "Rejected": 1})
    result = rows.search_rows("Candidates")
    assert result["total"] == 3


def test_fuzzy_finds_misspelled_name(repo):
    svc, rows = seed(repo, {"Applied": 2})
    rows.add_rows("Candidates", [{"name": "Rahul Sharma", "stage": "Applied"}])
    result = rows.search_rows("Candidates", fuzzy=True, query="Rahual", fuzzy_columns=["name"], fuzzy_threshold=70)
    assert result["total"] >= 1
    top = result["rows"][0]
    assert top["name"] == "Rahul Sharma" and top["_score"] >= 70


def test_fuzzy_requires_query(repo):
    svc, rows = seed(repo, {"Applied": 1})
    with pytest.raises(FilterError, match="non-empty query"):
        rows.search_rows("Candidates", fuzzy=True)


def test_query_without_fuzzy_rejected(repo):
    svc, rows = seed(repo, {"Applied": 1})
    with pytest.raises(FilterError, match="requires fuzzy"):
        rows.search_rows("Candidates", query="Rahul")


def test_fuzzy_unknown_text_column(repo):
    svc, rows = seed(repo, {"Applied": 1})
    with pytest.raises(FilterError, match="string/text columns"):
        rows.search_rows("Candidates", fuzzy=True, query="x", fuzzy_columns=["score"])


def test_fuzzy_combined_with_conditions(repo):
    svc, rows = seed(repo, {"Applied": 2})
    rows.add_rows("Candidates", [{"name": "Rahul Sharma", "stage": "Rejected"}])
    result = rows.search_rows(
        "Candidates",
        conditions=[{"column": "stage", "op": "eq", "value": "Applied"}],
        fuzzy=True,
        query="Rahual",
        fuzzy_columns=["name"],
        fuzzy_threshold=70,
    )
    assert result["total"] == 0


def test_summarize_dataset_aggregates(repo):
    svc, rows = seed(repo, {"Applied": 3, "Rejected": 1})
    result = rows.summarize_dataset("Candidates")
    assert result["row_count"] == 4
    assert result["numeric"]["score"]["count"] == 4
    assert result["numeric"]["score"]["min"] == 1
    assert result["numeric"]["score"]["max"] == 3
    assert result["enums"]["stage"] == {"Applied": 3, "Rejected": 1}
    assert "applied_on" not in result["numeric"]


def test_summarize_empty_dataset(repo):
    svc, rows = make_services(repo)
    svc.create_dataset("Empty", "", COLUMNS)
    result = rows.summarize_dataset("Empty")
    assert result["row_count"] == 0
    assert result["numeric"]["score"] == {"count": 0}
    assert result["enums"]["stage"] == {}
