"""考试引擎：组卷结构（按真题题型）、判分（客观自动 + 主观自评）。"""


def _content():
    def q(prefix, n, **extra):
        return [{"id": f"{prefix}{i}", "chapter": "T-01", "point_id": f"T-01-{i:02d}",
                 "stem": f"{prefix}题{i}", "options": ["a", "b", "c", "d"],
                 "answer": 0, "explain": "e", **extra} for i in range(1, n + 1)]

    def cards(kind, n):
        return [{"id": f"c{kind}{i}", "chapter": "T-01", "point_id": f"T-01-{i:02d}",
                 "front": f"{kind}卡{i}", "back": "b", "kind": kind} for i in range(1, n + 1)]

    ch = {"id": "T-01", "name": "测试章", "tier": 1, "weight_center": 10, "weight_range": [5, 15],
          "tags": [], "points": [{"id": f"T-01-{i:02d}", "text": f"点{i}", "spoken": "", "tags": [],
                                  "listen_ok": True, "media": [], "audio": []} for i in range(1, 41)],
          "quiz": q("s", 40) + q("m", 25, type="multi", answer=[0, 1]) + q("b", 22, type="blank", blanks=[{"accept": ["7"]}]),
          "cards": cards("名解", 8) + cards("简答", 8) + cards("论述", 5)}
    return {"version": "t", "subjects": [{"id": "315", "name": "化学", "has_content": True, "chapters": [ch]},
                                         {"id": "101", "name": "政治", "has_content": True, "chapters": [ch]},
                                         {"id": "812", "name": "生理", "has_content": True, "chapters": [ch]}]}


def test_assemble_315_structure():
    from app.services.exam_engine import assemble

    paper = assemble(_content(), "315", "objective")
    assert [s["type"] for s in paper["sections"]] == ["single", "blank"]
    assert len(paper["sections"][0]["items"]) == 30
    assert len(paper["sections"][1]["items"]) == 20
    assert paper["time_limit_min"] == 90
    assert all("chapter" in it for it in paper["sections"][0]["items"])


def test_assemble_101_structure():
    from app.services.exam_engine import assemble

    paper = assemble(_content(), "101", "objective")
    assert [s["type"] for s in paper["sections"]] == ["single", "multi"]
    assert len(paper["sections"][1]["items"]) == 17


def test_assemble_812_subjective_kinds():
    from app.services.exam_engine import assemble

    paper = assemble(_content(), "812", "subjective")
    kinds = [s.get("kind") for s in paper["sections"]]
    assert kinds == ["名解", "简答", "论述"]
    assert [len(s["items"]) for s in paper["sections"]] == [6, 6, 2]


def test_score_objective_and_multi_partial_zero():
    from app.services.exam_engine import assemble, score

    content = _content()
    paper = assemble(content, "315", "objective")
    sec_single, sec_blank = paper["sections"]
    responses = [{"item_id": it["id"], "response": 0} for it in sec_single["items"]]
    responses[0]["response"] = 1                                   # 错 1 题
    responses += [{"item_id": it["id"], "response": ["7"]} for it in sec_blank["items"]]
    r = score(content, paper, responses, [])
    assert r["score"] == 58 + 40                                   # 30×2-2 + 20×2
    assert r["per_section"]["选择题"]["earned"] == 58

    # 101 多选：部分对不计分
    paper101 = assemble(content, "101", "objective")
    resp = [{"item_id": it["id"], "response": 0} for it in paper101["sections"][0]["items"]]
    resp += [{"item_id": it["id"], "response": [0]} for it in paper101["sections"][1]["items"]]
    r = score(content, paper101, resp, [])
    assert r["per_section"]["多选题"]["earned"] == 0


def test_score_subjective_verdicts():
    from app.services.exam_engine import assemble, score

    content = _content()
    paper = assemble(content, "812", "subjective")
    verdicts = []
    for sec in paper["sections"]:
        for i, it in enumerate(sec["items"]):
            verdicts.append({"card_id": it["id"], "verdict": ["know", "fuzzy", "no"][i % 3]})
    r = score(content, paper, [], verdicts)
    # 名解 6 卡×5 分：know×2 + fuzzy×2(2.5) + no×2(0) = 15
    assert r["per_section"]["名词解释"]["earned"] == 15
    assert 0 < r["score"] < r["total"]


def test_score_per_chapter_breakdown():
    from app.services.exam_engine import assemble, score

    content = _content()
    paper = assemble(content, "315", "objective")
    responses = []
    for s in paper["sections"]:
        for it in s["items"]:
            responses.append({"item_id": it["id"],
                              "response": 0 if s["type"] == "single" else ["7"]})
    responses[0]["response"] = 1                       # 单选错 1 题
    r = score(content, paper, responses, [])
    assert r["per_chapter"]["T-01"]["n"] == 50
    assert r["per_chapter"]["T-01"]["correct"] == 49
