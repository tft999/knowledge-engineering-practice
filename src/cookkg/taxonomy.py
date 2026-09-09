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

    @model_validator(mode="after")
    def reviewed_categories_are_acyclic(self):
        parents = {
            relation.child: relation.parent
            for relation in self.categories
            if relation.reviewed
        }
        for start in parents:
            seen = set()
            current = start
            while current in parents:
                if current in seen:
                    raise ValueError("食材类别层级不能包含循环")
                seen.add(current)
                current = parents[current]
        return self


def load_taxonomy() -> Taxonomy:
    path = files("cookkg").joinpath("resources/taxonomy.json")
    return Taxonomy.model_validate(json.loads(path.read_text(encoding="utf-8")))
