"""Pure split-computation engine.

Given a rule and a transaction total, produce the split legs. Guarantees:

* Legs are computed in exact cents (Decimal), never binary floats.
* The signed legs always sum **exactly** to the transaction total.
* Sign is preserved: an expense (negative total) yields negative legs.

This module has no I/O and no GCP/Monarch dependencies, so it is trivially
unit-testable — which is where the correctness guarantees are enforced.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal

from dl_splitter.rules import FixedLeg, PercentageLeg, RemainderLeg, SplitRule

_CENTS = Decimal("0.01")


@dataclass(frozen=True)
class SplitLeg:
    name: str
    amount: float  # signed, rounded to cents
    category_id: str | None = None


class SplitError(ValueError):
    """Raised when a rule cannot produce a valid, balanced split."""


def _q(value: Decimal | float | int) -> Decimal:
    return Decimal(str(value)).quantize(_CENTS, rounding=ROUND_HALF_UP)


def compute_legs(rule: SplitRule, total: float) -> list[SplitLeg]:
    """Compute the split legs for ``rule`` applied to ``total``."""
    signed_total = _q(total)
    if signed_total == 0:
        raise SplitError(f"cannot split a zero-amount transaction (tag={rule.tag})")

    sign = Decimal(-1) if signed_total < 0 else Decimal(1)
    gross = abs(signed_total)

    magnitudes: list[Decimal] = []
    remainder_idx: int | None = None

    for i, leg in enumerate(rule.legs):
        if isinstance(leg, FixedLeg):
            magnitudes.append(_q(leg.amount))
        elif isinstance(leg, PercentageLeg):
            magnitudes.append(_q(gross * _q(leg.percent) / Decimal(100)))
        elif isinstance(leg, RemainderLeg):
            if remainder_idx is not None:
                raise SplitError(f"rule '{rule.tag}' has more than one remainder leg")
            remainder_idx = i
            magnitudes.append(Decimal(0))

    fixed_sum = sum((m for i, m in enumerate(magnitudes) if i != remainder_idx), start=Decimal(0))

    if remainder_idx is not None:
        remainder = _q(gross - fixed_sum)
        if remainder < 0:
            raise SplitError(
                f"rule '{rule.tag}': fixed/percentage legs ({fixed_sum}) exceed total ({gross})"
            )
        magnitudes[remainder_idx] = remainder
    else:
        # No remainder leg: reconcile any rounding drift onto the last leg so
        # the legs still sum exactly to the total.
        drift = _q(gross - fixed_sum)
        magnitudes[-1] = _q(magnitudes[-1] + drift)
        if magnitudes[-1] < 0:
            raise SplitError(
                f"rule '{rule.tag}': legs exceed total ({gross}); reconciliation went negative"
            )

    # Invariant: the split must balance to the penny.
    if sum(magnitudes, start=Decimal(0)) != gross:
        raise SplitError(f"rule '{rule.tag}': legs do not sum to total (internal error)")

    return [
        SplitLeg(name=leg.name, amount=float(sign * mag), category_id=leg.category_id)
        for leg, mag in zip(rule.legs, magnitudes, strict=True)
    ]
