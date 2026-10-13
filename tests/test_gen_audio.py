import json


def _content():
    return {"subjects": [
        {"id": "812", "has_content": True, "chapters": [{
            "id": "812-00", "points": [
                {"id": "812-00-01", "spoken": "短句。", "listen_ok": True},
                {"id": "812-00-02", "spoken": "很长的句子，" * 80, "listen_ok": True},
                {"id": "812-00-03", "spoken": "跳过我。", "listen_ok": False},
            ]}]},
        {"id": "101", "has_content": True, "chapters": [{
            "id": "101-01", "points": [{"id": "101-01-01", "spoken": "政治。", "listen_ok": True}]}]},
        {"id": "204", "has_content": False, "chapters": []},
    ]}


def test_clip_plan_multi_clip_and_skip():
    from scripts.gen_audio import clip_plan

    plan = clip_plan(_content())
    ids = [c["clip_id"] for c in plan]
    assert "812-00-01" in ids                       # 单段：原 id
    assert "812-00-02-p1" in ids and "812-00-02-p2" in ids  # 长句拆多段
    assert "812-00-03" not in ids                   # listen_ok=False 跳过
    assert "101-01-01" in ids


def test_clip_plan_only_filter():
    from scripts.gen_audio import clip_plan

    plan = clip_plan(_content(), only={"812"})
    assert all(c["subject"] == "812" for c in plan)


def test_qwen_audio_engine_writes_mp3_directly(tmp_path, monkeypatch):
    """qwen_audio 引擎：直接写 mp3、不走 wav/ffmpeg 路径，默认男声 longanyang。"""
    from scripts import gen_audio

    content = {"subjects": [{"id": "812", "has_content": True, "chapters": [{
        "id": "812-00", "points": [{"id": "812-00-01", "spoken": "短句。", "listen_ok": True}]}]}]}
    out = tmp_path / "audio"
    captured = {}

    def fake_qa(text, voice, settings, **kw):
        captured["voice"] = voice
        return b"mp3-bytes"

    monkeypatch.setattr(gen_audio, "synth_qwen_audio", fake_qa)
    monkeypatch.setattr(gen_audio, "probe_dur", lambda p: 7.5)
    monkeypatch.setattr(gen_audio, "load_settings", lambda: object())

    stats = gen_audio.generate(content, out, voice="Ethan", engine="qwen_audio")
    assert stats["done"] == 1
    assert (out / "812-00-01.mp3").read_bytes() == b"mp3-bytes"
    assert captured["voice"] is None  # Ethan 是 bailian 默认名 → 交给引擎默认男声
    assert content["subjects"][0]["chapters"][0]["points"][0]["audio"][0]["dur"] == 7.5


def test_generate_skips_existing_and_records_failure(tmp_path, monkeypatch):
    from scripts import gen_audio

    content = _content()
    out = tmp_path / "audio"
    out.mkdir()
    (out / "812-00-01.mp3").write_bytes(b"exists")   # 已存在 → 跳过

    calls = []
    seen = {"long": 0}

    def fake_synth(text, voice, settings, **kw):
        calls.append(text)
        if "很长的句子" in text:
            seen["long"] += 1
            if seen["long"] == 1:          # 只让第一段失败，验证续跑能力
                raise RuntimeError("api down")
        return b"wav-bytes"

    def fake_wav_to_mp3(wav, mp3):
        mp3.write_bytes(wav)
        return 12.5

    monkeypatch.setattr(gen_audio, "synth", fake_synth)
    monkeypatch.setattr(gen_audio, "wav_to_mp3", fake_wav_to_mp3)
    monkeypatch.setattr(gen_audio, "load_settings", lambda: object())

    stats = gen_audio.generate(content, out, voice="Ethan")
    assert stats["done"] >= 2 and stats["failed"] >= 1
    assert not any("短句" in c for c in calls)       # 已存在未重跑
    failed = json.loads((out.parent / "audio_failed.json").read_text()) if (out.parent / "audio_failed.json").exists() else []
    assert any(f["clip_id"].startswith("812-00-02") for f in failed)
    # 回填 audio 数组
    pts = content["subjects"][0]["chapters"][0]["points"]
    assert pts[0]["audio"] and pts[0]["audio"][0]["src"] == "audio/812-00-01.mp3"
