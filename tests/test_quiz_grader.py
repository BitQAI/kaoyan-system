def test_grade_single():
    from app.services.quiz_grader import grade

    q = {"type": "single", "options": ["a", "b", "c", "d"], "answer": 2}
    assert grade(q, 2)["correct"] is True
    assert grade(q, 1)["correct"] is False


def test_grade_multi_all_or_nothing():
    from app.services.quiz_grader import grade

    q = {"type": "multi", "options": ["a", "b", "c", "d"], "answer": [0, 2]}
    assert grade(q, [0, 2])["correct"] is True          # 全对
    assert grade(q, [0])["correct"] is False             # 少选
    assert grade(q, [0, 2, 1])["correct"] is False       # 多选
    assert grade(q, [])["correct"] is False              # 空提交
    assert grade(q, [2, 0])["correct"] is True           # 顺序无关


def test_grade_blank_variants():
    from app.services.quiz_grader import grade

    q = {"type": "blank", "blanks": [{"accept": ["1.8×10-5", "1.8x10^-5"]}]}
    assert grade(q, ["1.8×10⁻⁵"])["correct"] is True     # 上标 ⁻⁵ → -5
    assert grade(q, [" 1.8X10-5 "])["correct"] is True    # 空格/大小写
    assert grade(q, ["1.8*10-5"])["correct"] is True
    assert grade(q, ["2.0×10-5"])["correct"] is False


def test_grade_blank_multiple_partial_is_wrong():
    from app.services.quiz_grader import grade

    q = {"type": "blank", "blanks": [{"accept": ["A"]}, {"accept": ["B"]}]}
    assert grade(q, ["A", "B"])["correct"] is True
    assert grade(q, ["A", "X"])["correct"] is False
    assert grade(q, ["A"])["correct"] is False            # 空数不对


def test_grade_legacy_no_type_is_single():
    from app.services.quiz_grader import grade

    q = {"options": ["a", "b"], "answer": 1}
    assert grade(q, 1)["correct"] is True
    assert grade(q, 0)["correct"] is False


def test_normalize_blank_cjk_and_units():
    from app.services.quiz_grader import normalize_blank

    assert normalize_blank("（ 1.8 × 10⁻⁵ ）") == "(1.8*10-5)"
    assert normalize_blank("KMnO₄") == normalize_blank("KMnO4")
