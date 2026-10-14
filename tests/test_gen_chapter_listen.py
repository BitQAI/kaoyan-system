def _content():
    return {"subjects": [
        {"id": "315", "has_content": True, "chapters": [{
            "id": "315-01", "weight_center": 3,
            "points": [{"id": "315-01-01", "text": "点一", "spoken": "点一。", "audio": [{"src": "audio/315-01-01.mp3", "dur": 3}]},
                       {"id": "315-01-02", "text": "点二" * 220, "spoken": "点二" * 220 + "。", "audio": []}],
            "listen": [], "quiz": [], "cards": []}]},
        {"id": "812", "has_content": True, "chapters": [{
            "id": "812-00", "points": [{"id": "812-00-01", "spoken": "x", "audio": []}], "quiz": [], "cards": []}]},
    ]}


def test_build_chapter_spoken_merges_intro_and_points():
    from scripts.gen_chapter_listen import build_chapter_spoken

    chap = {"id": "315-01", "points": [{"spoken": "甲概念。"}, {"spoken": "乙特点。"}]}
    s = build_chapter_spoken(chap, "第一章导览语。", subject="315")
    assert s.startswith("第一章导览语") and "甲概念" in s and "乙特点" in s


def test_generate_fills_listen_and_clears_point_audio(tmp_path, monkeypatch):
    from scripts import gen_chapter_listen as g

    content = _content()
    out = tmp_path / "audio"
    out.mkdir()
    calls = []

    def fake_synth(text, voice, settings, **kw):
        calls.append(text)
        return b"mp3"

    monkeypatch.setattr(g, "synth_qwen_audio", fake_synth)
    monkeypatch.setattr(g, "probe_dur", lambda p: 30.0)
    monkeypatch.setattr(g, "load_settings", lambda: object())
    monkeypatch.setattr(g, "CHAPTER_INTROS", {"315-01": "导览。"})

    stats = g.generate(content, out, sleep_between=0)
    chap = content["subjects"][0]["chapters"][0]
    assert chap["listen"] and chap["listen"][0]["point_ids"] == ["315-01-01", "315-01-02"]
    assert all(c["src"].startswith("audio/315-01-c") for c in chap["listen"])
    assert chap["points"][0]["audio"] == []                    # 点级下线
    assert stats["chapters"] == 1
    # 812 不处理
    assert content["subjects"][1]["chapters"][0].get("listen") in (None, [])

    # 幂等：第二次运行跳过（无新合成调用）
    n_calls = len(calls)
    g.generate(content, out, sleep_between=0)
    assert len(calls) == n_calls


def test_long_chapter_splits_into_multiple_clips(tmp_path, monkeypatch):
    from scripts import gen_chapter_listen as g

    content = _content()
    out = tmp_path / "audio"
    out.mkdir()

    monkeypatch.setattr(g, "synth_qwen_audio", lambda t, v, s, **kw: b"mp3")
    monkeypatch.setattr(g, "probe_dur", lambda p: 50.0)
    monkeypatch.setattr(g, "load_settings", lambda: object())
    monkeypatch.setattr(g, "CHAPTER_INTROS", {"315-01": "导览。"})

    g.generate(content, out, sleep_between=0)
    chap = content["subjects"][0]["chapters"][0]
    assert len(chap["listen"]) >= 2                            # 超长点触发多段
    assert chap["listen"][1]["src"].endswith("-c2.mp3")
