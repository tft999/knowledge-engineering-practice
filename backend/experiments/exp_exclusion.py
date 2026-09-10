"""实验一：忌口推理对照。

比较四种方法识别忌口冲突的能力：

1. keyword     —— 关键词精确匹配；
2. alias       —— 别名归一化；
3. taxonomy    —— 食材层级图谱推理；
4. component   —— 层级图谱 + 经审核的复合食材成分推理。

指标：对每个「(菜谱, 排除项)」样例，判断该菜谱是否应被淘汰，
统计准确率、召回率、F1、误排除率。
"""

from __future__ import annotations

from cookkg.exclusion import expand_exclusions
from cookkg.filter import filter_recipe
from cookkg.models import Recipe

from .common import EvalMetadata, build_engine, save_result

# 人工标注的真值：(菜谱 ID, 排除项, 是否应淘汰)
# 真值以“最完整知识”（含成分关系）为准：淘汰 = 必需食材或必需选择组命中排除。
# 关键词/别名/层级方法会因缺少层级或成分推理而漏检，从而体现召回率递进。
GROUND_TRUTH: list[tuple[str, str, bool]] = [
    ("dishes/meat_dish/小炒肉.md", "辣椒", True),  # 必需小米椒 IS_A 辣椒
    ("dishes/meat_dish/小炒肉.md", "小米椒", True),  # 精确命中必需食材
    ("dishes/vegetable_dish/酸辣土豆丝.md", "辣椒", False),  # 辣椒为可选 -> 省略不淘汰
    ("dishes/meat_dish/回锅肉.md", "辣椒", True),  # 必需豆瓣酱 HAS_COMPONENT 辣椒
    ("dishes/vegetable_dish/番茄炒蛋.md", "辣椒", False),  # 无关
]


def _keyword_excluded(recipe: Recipe, exclude: str) -> bool:
    """关键词精确匹配：菜谱食材名必须与排除项完全一致才算命中。"""
    for ing in recipe.ingredients:
        if ing.id == exclude and ing.requirement == "required":
            return True
    return False


def _run(method: str, use_component: bool = False) -> dict:
    engine = build_engine(use_component)
    tp = fp = tn = fn = 0
    for recipe_id, exclude, expected_excluded in GROUND_TRUTH:
        recipe = next(r for r in engine.recipes if r.id == recipe_id)
        if method == "keyword":
            excluded = _keyword_excluded(recipe, exclude)
        else:
            norm = engine.normalizer.normalize(exclude)
            if method == "alias":
                # 别名归一化：归一化后做精确匹配，不做层级扩展
                excluded = _keyword_excluded(recipe, norm)
            else:
                exclusion = expand_exclusions(
                    [exclude],
                    engine.taxonomy,
                    engine.normalizer,
                    use_component=(method == "component"),
                )
                result = filter_recipe(recipe, exclusion, set(), set())
                excluded = not result.retained
        if expected_excluded and excluded:
            tp += 1
        elif expected_excluded and not excluded:
            fn += 1
        elif not expected_excluded and excluded:
            fp += 1
        else:
            tn += 1

    precision = tp / (tp + fp) if (tp + fp) else 0.0
    recall = tp / (tp + fn) if (tp + fn) else 0.0
    f1 = 2 * precision * recall / (precision + recall) if (precision + recall) else 0.0
    return {
        "method": method,
        "tp": tp,
        "fp": fp,
        "tn": tn,
        "fn": fn,
        "precision": round(precision, 4),
        "recall": round(recall, 4),
        "f1": round(f1, 4),
        "false_exclusion_rate": round(fp / (fp + tn), 4) if (fp + tn) else 0.0,
    }


def run() -> list[dict]:
    return [_run("keyword"), _run("alias"), _run("taxonomy"), _run("component")]


if __name__ == "__main__":
    rows = run()
    save_result("exp_exclusion", EvalMetadata(experiment="exclusion"), rows)
    for r in rows:
        print(r)
