from typing import Any

import pytest
from dl_splitter.engine import SplitError, SplitLeg, compute_legs
from dl_splitter.rules import SplitRule


def _rule(*legs: dict[str, Any]) -> SplitRule:
    return SplitRule.model_validate({"tag": "split:test", "legs": list(legs)})


def _sum(legs: list[SplitLeg]) -> float:
    return round(sum(leg.amount for leg in legs), 2)


def test_fixed_plus_remainder_expense_is_negative_and_balances() -> None:
    rule = _rule(
        {"type": "fixed", "name": "mine", "amount": 1500.00},
        {"type": "remainder", "name": "roommate"},
    )
    legs = compute_legs(rule, -2000.00)
    assert [leg.amount for leg in legs] == [-1500.00, -500.00]
    assert _sum(legs) == -2000.00


def test_percentage_plus_remainder() -> None:
    rule = _rule(
        {"type": "percentage", "name": "household", "percent": 60},
        {"type": "remainder", "name": "personal"},
    )
    legs = compute_legs(rule, -100.00)
    assert [leg.amount for leg in legs] == [-60.00, -40.00]
    assert _sum(legs) == -100.00


def test_mixed_fixed_and_percentage_with_remainder() -> None:
    rule = _rule(
        {"type": "fixed", "name": "a", "amount": 25.00},
        {"type": "percentage", "name": "b", "percent": 50},
        {"type": "remainder", "name": "c"},
    )
    legs = compute_legs(rule, -100.00)  # 25 + 50 + remainder(25)
    assert [leg.amount for leg in legs] == [-25.00, -50.00, -25.00]
    assert _sum(legs) == -100.00


def test_rounding_reconciled_onto_remainder() -> None:
    # 33.33% of 100 = 33.33 each; remainder absorbs the extra penny.
    rule = _rule(
        {"type": "percentage", "name": "a", "percent": 33.33},
        {"type": "percentage", "name": "b", "percent": 33.33},
        {"type": "remainder", "name": "c"},
    )
    legs = compute_legs(rule, 100.00)
    assert [leg.amount for leg in legs] == [33.33, 33.33, 33.34]
    assert _sum(legs) == 100.00


def test_no_remainder_reconciles_rounding_onto_last_leg() -> None:
    rule = _rule(
        {"type": "percentage", "name": "a", "percent": 33.33},
        {"type": "percentage", "name": "b", "percent": 66.67},
    )
    legs = compute_legs(rule, 100.00)
    assert _sum(legs) == 100.00


def test_income_positive_sign_preserved() -> None:
    rule = _rule(
        {"type": "fixed", "name": "a", "amount": 30.00},
        {"type": "remainder", "name": "b"},
    )
    legs = compute_legs(rule, 100.00)
    assert all(leg.amount > 0 for leg in legs)
    assert _sum(legs) == 100.00


def test_category_id_passthrough() -> None:
    rule = _rule(
        {"type": "fixed", "name": "a", "amount": 10.0, "category_id": "cat_1"},
        {"type": "remainder", "name": "b", "category_id": "cat_2"},
    )
    legs = compute_legs(rule, 50.0)
    assert legs[0].category_id == "cat_1"
    assert legs[1].category_id == "cat_2"


def test_fixed_exceeding_total_raises() -> None:
    rule = _rule(
        {"type": "fixed", "name": "a", "amount": 999.00},
        {"type": "remainder", "name": "b"},
    )
    with pytest.raises(SplitError):
        compute_legs(rule, -100.00)


def test_multiple_remainder_legs_rejected() -> None:
    rule = _rule(
        {"type": "remainder", "name": "a"},
        {"type": "remainder", "name": "b"},
    )
    with pytest.raises(SplitError):
        compute_legs(rule, -100.00)


def test_zero_total_rejected() -> None:
    rule = _rule({"type": "remainder", "name": "a"})
    with pytest.raises(SplitError):
        compute_legs(rule, 0.0)
