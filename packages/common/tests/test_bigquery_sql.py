from dl_common.bigquery import BigQueryClient


def test_merge_sql_includes_soft_delete_clause() -> None:
    sql = BigQueryClient._merge_sql("proj.raw.transactions", "proj.raw._stg", soft_delete=True)
    assert "MERGE `proj.raw.transactions` T" in sql
    assert "NOT MATCHED BY TARGET" in sql
    assert "NOT MATCHED BY SOURCE" in sql
    assert "_is_deleted = TRUE" in sql
    assert "PARSE_JSON(S.data)" in sql


def test_merge_sql_omits_soft_delete_when_disabled() -> None:
    sql = BigQueryClient._merge_sql("proj.raw.budgets", "proj.raw._stg", soft_delete=False)
    assert "NOT MATCHED BY SOURCE" not in sql
    assert "NOT MATCHED BY TARGET" in sql
