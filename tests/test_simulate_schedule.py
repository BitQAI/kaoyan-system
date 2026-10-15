"""负载模拟脚本：验收 Spec §7.2 的阈值。测试先行。"""


def test_simulation_meets_spec_thresholds():
    from scripts.simulate_schedule import simulate

    out = simulate(cap=260, learn_days=45)
    assert out["daily_avg"] <= 180          # Spec §7.2：均值不得超原批准预算
    assert out["peak"] <= 260
    assert out["tier_tail_coverage"][1] >= 0.95
    assert out["tier_tail_coverage"][2] >= 0.90
    assert out["tier_tail_coverage"][3] >= 0.40   # 第 3 梯队有意饥饿，仅设下限


def test_simulation_uses_engine_formula_not_a_copy():
    """脚本与实现共用同一公式：改 K 表，脚本结果随之变化。"""
    from app.services import unit_review_engine as e
    from scripts.simulate_schedule import simulate

    before = simulate(cap=260, learn_days=45)["total_reviews"]
    saved = e.K_BY_TIER[1]
    try:
        e.K_BY_TIER[1] = 2
        after = simulate(cap=260, learn_days=45)["total_reviews"]
    finally:
        e.K_BY_TIER[1] = saved
    assert after < before                   # 别无脑复制公式，否则这里不变
