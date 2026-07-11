"""Split-rule config models and loading.

Rules are keyed by the Monarch tag that triggers them. Each rule has an ordered
list of legs; a leg is a fixed dollar amount, a percentage of the total, or the
remainder. Pydantic validates the config on load.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Annotated, Literal

import yaml
from pydantic import BaseModel, Field

_DEFAULT_RULES_PATH = Path(__file__).resolve().parents[2] / "split_rules.yaml"


class FixedLeg(BaseModel):
    type: Literal["fixed"]
    name: str
    amount: float = Field(gt=0)
    category_id: str | None = None


class PercentageLeg(BaseModel):
    type: Literal["percentage"]
    name: str
    percent: float = Field(gt=0, le=100)
    category_id: str | None = None


class RemainderLeg(BaseModel):
    type: Literal["remainder"]
    name: str
    category_id: str | None = None


Leg = Annotated[FixedLeg | PercentageLeg | RemainderLeg, Field(discriminator="type")]


class SplitRule(BaseModel):
    tag: str
    legs: list[Leg] = Field(min_length=1)


class SplitRules(BaseModel):
    rules: list[SplitRule] = Field(default_factory=list)

    def for_tag(self, tag: str) -> SplitRule | None:
        return next((r for r in self.rules if r.tag == tag), None)

    @property
    def trigger_tags(self) -> set[str]:
        return {r.tag for r in self.rules}


def load_rules(path: str | os.PathLike[str] | None = None) -> SplitRules:
    """Load and validate split rules. Path resolution order: arg, env, default."""
    resolved = Path(path or os.environ.get("SPLIT_RULES_PATH") or _DEFAULT_RULES_PATH)
    with open(resolved, encoding="utf-8") as fh:
        raw = yaml.safe_load(fh) or {}
    return SplitRules.model_validate(raw)
