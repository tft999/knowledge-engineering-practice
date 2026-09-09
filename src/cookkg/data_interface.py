"""Small data-to-UI DTO adapter for the backend owner; no menu-ranking logic."""

from cookkg.data_models import DataRecipe


def recipe_detail(recipe: DataRecipe | dict) -> dict:
    """Map approved data to web/src/api/types.ts RecipeDetail.

    Unknown relationships have no representation in that UI contract. Refuse
    draft data instead of silently omitting or turning them into required items.
    The backend still owns routing, recommendation and graph explanations.
    """
    record = DataRecipe.model_validate(recipe)
    if not record.strict_eligible:
        raise ValueError("Recipe is not eligible for the strict public data interface")
    return dict(id=record.id, name=record.name, source_url=record.source_url,
                category=record.category, difficulty=record.difficulty, steps=record.steps,
                ingredients=[dict(name=u.id, requirement=u.requirement,
                                  quantity_raw=u.quantity_raw) for u in record.ingredients])
