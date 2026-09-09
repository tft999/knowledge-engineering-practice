import hashlib
import json
from importlib.resources import files
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class Membership(BaseModel):
    model_config = ConfigDict(extra="forbid")
    ingredient: str = Field(min_length=1)
    category: str = Field(min_length=1)
    reviewed: bool
    evidence: str = Field(min_length=1)


class CategoryRelation(BaseModel):
    model_config = ConfigDict(extra="forbid")
    child: str = Field(min_length=1)
    parent: str = Field(min_length=1)
    reviewed: bool
    evidence: str = Field(min_length=1)


class Taxonomy(BaseModel):
    model_config = ConfigDict(extra="forbid")
    version: Literal["1.0"]
    memberships: list[Membership] = Field(default_factory=list)
    categories: list[CategoryRelation] = Field(default_factory=list)

    def digest(self) -> str:
        payload = json.dumps(
            self.model_dump(mode="json"),
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        )
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()

    @model_validator(mode="after")
    def reviewed_categories_are_acyclic(self):
        parents: dict[str, set[str]] = {}
        for relation in self.categories:
            if relation.reviewed:
                parents.setdefault(relation.child, set()).add(relation.parent)

        states: dict[str, int] = {}

        def visit(category: str) -> None:
            if states.get(category) == 1:
                raise ValueError("食材类别层级不能包含循环")
            if states.get(category) == 2:
                return
            states[category] = 1
            for parent in sorted(parents.get(category, set())):
                visit(parent)
            states[category] = 2

        for category in sorted(parents):
            visit(category)
        return self


def load_taxonomy() -> Taxonomy:
    path = files("cookkg").joinpath("resources/taxonomy.json")
    return Taxonomy.model_validate(json.loads(path.read_text(encoding="utf-8")))
