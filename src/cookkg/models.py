from typing import Literal

from pydantic import BaseModel, Field

IngredientStatus = Literal["required", "optional", "pending"]


class IngredientUse(BaseModel):
    name: str
    status: IngredientStatus
    quantity_raw: list[str] = Field(default_factory=list)
    evidence: list[str] = Field(default_factory=list)


class Recipe(BaseModel):
    id: str
    name: str
    category: str
    source_url: str
    source_hash: str
    difficulty: int | None = None
    ingredients: list[IngredientUse] = Field(default_factory=list)
    tools: list[str] = Field(default_factory=list)
    steps: str = ""
    reviewed: bool = False
    eligible: bool = True


class ParseResult(BaseModel):
    recipe: Recipe
    issues: list[str] = Field(default_factory=list)
    skipped: bool = False
