def test_to_speech_symbols():
    from scripts.normalize import to_speech

    s = to_speech("水势 Ψ_w = Ψ_s+Ψ_p，ΔG<0 时反应自发，KMnO₄ 氧化，H⁺-ATP 酶供能。")
    assert "水势" in s and "德尔塔" in s and "高锰酸钾" in s and "氢离子" in s
    assert "Ψ" not in s and "Δ" not in s and "₄" not in s


def test_chem_formulas_315():
    from scripts.normalize import to_speech

    s = to_speech("CH₃CH₂OH → CH₂=CH₂，K₂Cr₂O₇ 氧化，C₄ 草酰乙酸。", subject="315")
    assert "高锰酸钾" not in s
    assert "重铬酸钾" in s and "生成" in s


def test_arrow_context_by_subject():
    from scripts.normalize import to_speech

    s812 = to_speech("刺激→保卫细胞膨压变化→气孔开闭。", subject="812")
    assert "生成" not in s812 and "到" in s812


def test_split_clips_cap_and_boundary():
    from scripts.normalize import split_clips

    t = "光合作用分三个阶段。" + "第一阶段是原初反应，完成光能吸收传递与激发；" * 6
    clips = split_clips(t, 120)
    assert len(clips) >= 3
    assert all(len(c) <= 120 for c in clips)
    assert clips[0].startswith("光合作用分三个阶段")


def test_split_clips_long_sentence_hard_cut():
    from scripts.normalize import split_clips

    t = "很长的一句话没有逗号" * 30  # 300 字无标点
    clips = split_clips(t, 120)
    assert all(len(c) <= 120 for c in clips)
    assert "".join(clips) == t


def test_no_leftover_common_symbols():
    from scripts.normalize import to_speech

    s = to_speech("温度 25℃ 时，光补偿点≈10，波长 660nm，α-淀粉酶活性≥90%。")
    assert "℃" not in s and "≈" not in s and "≥" not in s
