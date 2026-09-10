"""联合补购优化测试。"""

from cookkg.models import RecommendRequest


def test_core_demo_returns_plans(engine):
    resp = engine.recommend(
        RecommendRequest(
            have=["鸡蛋", "土豆", "西红柿"],
            pantry=["盐", "食用油", "生抽"],
            exclude=["辣椒"],
            count=2,
            max_buy=2,
            limit=5,
        )
    )
    assert resp.plans, resp.reason
    for plan in resp.plans:
        assert plan.buy_count <= 2
        # 每个方案的补购种类与 buy 列表一致
        assert plan.buy_count == len(plan.buy)
    # 排除“辣椒”应包含下位食材“小米椒”
    assert "小米椒" in resp.excluded_ingredients


def test_shared_missing_counted_once(engine):
    # 番茄炒蛋 + 西红柿鸡蛋汤 都需要西红柿、鸡蛋、盐；合并去重
    resp = engine.recommend(
        RecommendRequest(
            have=["鸡蛋"],
            pantry=["盐"],
            exclude=[],
            count=2,
            max_buy=2,
            limit=5,
        )
    )
    combo = [p for p in resp.plans if {r.id for r in p.recipes} == {
        "dishes/vegetable_dish/番茄炒蛋.md",
        "dishes/soup/西红柿鸡蛋汤.md",
    }]
    assert combo, resp.reason
    plan = combo[0]
    # 两菜需西红柿、食用油；鸡蛋、盐有库存/常备；共享西红柿只买一次
    assert plan.buy == ["西红柿", "食用油"]
    assert plan.buy_count == 2


def test_max_buy_constraint(engine):
    resp = engine.recommend(
        RecommendRequest(have=[], pantry=[], exclude=[], count=3, max_buy=0, limit=5)
    )
    # 无库存无调料时任何菜都需要补购，max_buy=0 应无解
    assert resp.plans == []
    assert resp.reason is not None


def test_no_solution_reports_reason(engine):
    resp = engine.recommend(
        RecommendRequest(have=[], pantry=[], exclude=["辣椒"], count=1, max_buy=1, limit=5)
    )
    assert resp.reason is not None


def test_deterministic_ordering(engine):
    req = RecommendRequest(
        have=["鸡蛋"], pantry=["盐", "食用油"], exclude=["辣椒"], count=2, max_buy=3, limit=5
    )
    r1 = engine.recommend(req)
    r2 = engine.recommend(req)
    assert [p.recipes for p in r1.plans] == [p.recipes for p in r2.plans]


def test_count_bounds(engine):
    # count=1 应能返回单菜方案
    resp = engine.recommend(
        RecommendRequest(
            have=["鸡蛋", "西红柿"],
            pantry=["盐", "食用油"],
            exclude=["辣椒"],
            count=1,
            max_buy=2,
            limit=5,
        )
    )
    assert resp.plans
    assert all(len(p.recipes) == 1 for p in resp.plans)
