"""Versioned, source-grounded data contract; independent of the v0.1 recommender."""

import re
from datetime import date
from pathlib import PurePosixPath
from typing import Literal, Self

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

ReviewState = Literal["pending", "confirmed"]
Requirement = Literal["required", "optional", "one_of", "unknown"]


def validate_recipe_id(value: str) -> str:
    path = PurePosixPath(value)
    if (not value.startswith("dishes/") or "\\" in value or ":" in value
            or ".." in path.parts or path.as_posix() != value or path.suffix != ".md"):
        raise ValueError(f"Invalid recipe path: {value}")
    return value


class Record(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class Evidence(Record):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=False)
    line: int = Field(ge=1)
    text: str = Field(min_length=1)


class Quantity(Record):
    """One source observation; never a summed recipe total or unit conversion."""

    kind: Literal["exact", "range", "adjustable", "formula", "qualitative", "unparsed"]
    scope: Literal["ingredient", "combined", "context"] = "ingredient"
    raw: str = Field(min_length=1)
    value: float | None = Field(default=None, ge=0, allow_inf_nan=False)
    minimum: float | None = Field(default=None, ge=0, allow_inf_nan=False)
    maximum: float | None = Field(default=None, ge=0, allow_inf_nan=False)
    adjustment: float | None = Field(default=None, ge=0, allow_inf_nan=False)
    unit: str | None = None
    formula: str | None = None
    approximate: bool = False
    member_ids: list[str] = Field(default_factory=list)
    evidence: Evidence

    @model_validator(mode="after")
    def semantics(self) -> Self:
        if self.raw not in self.evidence.text:
            raise ValueError("Quantity text must be an exact source substring")
        if self.kind == "exact" and (self.value is None or not self.unit):
            raise ValueError("Exact quantity needs a value and unit")
        if self.kind == "range" and (self.minimum is None or self.maximum is None
                                     or self.minimum > self.maximum or not self.unit):
            raise ValueError("Invalid quantity range")
        if self.kind == "adjustable" and (self.value is None or self.adjustment is None
                                          or not self.unit):
            raise ValueError("Adjustable quantity needs a base, adjustment and unit")
        if self.kind == "formula" and not self.formula:
            raise ValueError("Formula quantity needs the original expression")
        if self.scope == "combined" and len(self.member_ids) < 2:
            raise ValueError("Combined quantity needs at least two ingredient IDs")
        if self.scope == "context" and self.kind != "unparsed":
            raise ValueError("Unassigned context cannot become a numeric ingredient quantity")
        if self.kind in {"formula", "qualitative", "unparsed"} and any(
            v is not None for v in [self.value, self.minimum, self.maximum, self.adjustment]
        ):
            raise ValueError("Unevaluated quantity cannot claim numeric values")
        expected = ([self.value] if self.kind == "exact" else
                    [self.minimum, self.maximum] if self.kind == "range" else
                    [self.value, self.adjustment] if self.kind == "adjustable" else [])
        observed = [float(n) for n in re.findall(r"\d+(?:\.\d+)?|\.\d+", self.raw)]
        if expected and observed != expected:
            raise ValueError("Numeric quantity differs from its source expression")
        if expected and self.unit not in self.raw:
            raise ValueError("Quantity unit is absent from source expression")
        return self


class Preparation(Record):
    form: str = Field(min_length=1)
    evidence: Evidence

    @model_validator(mode="after")
    def grounded(self) -> Self:
        if self.form not in self.evidence.text:
            raise ValueError("Preparation form must appear in evidence")
        return self


class Use(Record):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=False)
    use_id: str = Field(min_length=1)
    id: str = Field(min_length=1)
    surface: str = Field(min_length=1)
    requirement: Requirement
    review_state: ReviewState = "pending"
    group_id: str | None = None
    resource_kind: Literal["food", "household_resource"] = "food"
    quantity_raw: list[str] = Field(default_factory=list)
    quantities: list[Quantity] = Field(default_factory=list)
    forms: list[Preparation] = Field(default_factory=list)
    evidence: list[Evidence] = Field(min_length=1)


class ToolUse(Record):
    use_id: str
    id: str = Field(min_length=1)
    requirement: Literal["required", "optional", "one_of"] = "required"
    group_id: str | None = None
    review_state: ReviewState = "pending"
    evidence: list[Evidence] = Field(min_length=1)


class ChoiceGroup(Record):
    id: str = Field(min_length=1)
    kind: Literal["food", "tool"] = "food"
    member_ids: list[str] = Field(min_length=1)
    min_select: int = Field(ge=0)
    max_select: int = Field(ge=1)
    is_open: bool = False
    evidence: list[Evidence] = Field(min_length=1)

    @model_validator(mode="after")
    def bounds(self) -> Self:
        if not self.min_select <= self.max_select <= len(self.member_ids):
            raise ValueError("Invalid choice bounds")
        if len(set(self.member_ids)) != len(self.member_ids):
            raise ValueError("Duplicate choice members")
        return self


class Issue(Record):
    code: str
    detail: str
    evidence: list[Evidence] = Field(min_length=1)


class Annotation(Record):
    schema_version: Literal["2.0"] = "2.0"
    id: str
    source_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    method: Literal["ai_assisted", "human"] = "ai_assisted"
    author: str = "Codex (AI assistance for Zouyilin06)"
    ingredients: list[Use] = Field(min_length=1)
    tools: list[ToolUse] = Field(default_factory=list)
    choice_groups: list[ChoiceGroup] = Field(default_factory=list)
    issues: list[Issue] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)

    _valid_id = field_validator("id")(validate_recipe_id)

    @model_validator(mode="after")
    def references(self) -> Self:
        if not self.author.strip():
            raise ValueError("Annotation author is required")
        uses = [*self.ingredients, *self.tools]
        by_id = {item.use_id: item for item in uses}
        groups = {group.id: group for group in self.choice_groups}
        if len(by_id) != len(uses) or len(groups) != len(self.choice_groups):
            raise ValueError("Duplicate use or group ID")
        identities = [(u.id, u.group_id) for u in self.ingredients]
        if len(set(identities)) != len(identities):
            raise ValueError("Duplicate ingredient within a group or base recipe")
        for use in uses:
            if (use.requirement == "one_of") != (use.group_id is not None):
                raise ValueError("one_of requires a group; other uses cannot have a group")
            if use.group_id is not None and use.group_id not in groups:
                raise ValueError("Dangling group reference")
            if isinstance(use, Use):
                if (use.id == "水") != (use.resource_kind == "household_resource"):
                    raise ValueError("Only water is a household resource in v2")
            if (self.method == "ai_assisted" and use.review_state != "pending"
                    and not getattr(self, "human_approval", None)):
                raise ValueError("AI annotations cannot self-confirm")
        for group in self.choice_groups:
            actual = {u.use_id for u in uses if u.group_id == group.id}
            if actual != set(group.member_ids):
                raise ValueError("Choice membership differs from use references")
            for uid in actual:
                if (group.kind == "food") != isinstance(by_id[uid], Use):
                    raise ValueError("Cannot mix tools and food in one choice")
        return self


class HumanApproval(Record):
    reviewer: str = Field(min_length=1)
    reviewed_on: date
    source_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    annotation_hash: str = Field(pattern=r"^[0-9a-f]{64}$")


class Approvals(Record):
    standard_frozen: bool = False
    ontology_hash: str | None = None
    ontology_reviewer: str | None = None
    ontology_reviewed_on: date | None = None
    recipes: dict[str, HumanApproval] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_ids(self) -> Self:
        for recipe_id in self.recipes:
            validate_recipe_id(recipe_id)
        if self.standard_frozen and not (
            self.ontology_hash and self.ontology_reviewer and self.ontology_reviewed_on
        ):
            raise ValueError("Frozen standard needs an ontology reviewer, date and hash")
        return self


class DataRecipe(Annotation):
    """Exported recipe; its human approval is separate from annotation authorship."""

    name: str
    category: str
    difficulty: int | None = Field(default=None, ge=1, le=5)
    source_commit: str = Field(pattern=r"^[0-9a-f]{40}$")
    source_url: str
    steps: str
    annotation_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    review_state: ReviewState = "pending"
    human_approval: HumanApproval | None = None
    strict_eligible: bool = False

    @model_validator(mode="after")
    def approval_required(self) -> Self:
        if (self.review_state == "confirmed") != (self.human_approval is not None):
            raise ValueError("Recipe confirmation requires human approval")
        if self.human_approval and (
            self.human_approval.source_hash != self.source_hash
            or self.human_approval.annotation_hash != self.annotation_hash
        ):
            raise ValueError("Mismatched human approval")
        if self.strict_eligible and (
            not self.human_approval or self.issues or any(g.is_open for g in self.choice_groups)
            or any(u.requirement == "unknown" or u.review_state != "confirmed"
                   for u in self.ingredients)
        ):
            raise ValueError("Unresolved recipe cannot enter strict data")
        return self
