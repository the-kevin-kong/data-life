from dl_monarch.client import _extract


def test_extract_nested_list() -> None:
    resp = {"allTransactions": {"results": [{"id": "1"}, {"id": "2"}]}}
    assert _extract(resp, "allTransactions", "results") == [{"id": "1"}, {"id": "2"}]


def test_extract_missing_key_returns_empty_list() -> None:
    assert _extract({"a": {}}, "a", "missing") == []
    assert _extract({}, "nope") == []


def test_extract_none_leaf_returns_empty_list() -> None:
    assert _extract({"a": None}, "a") == []
