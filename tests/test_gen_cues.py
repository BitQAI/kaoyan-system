"""gen_cues 回复解析的边界测试（与 test_gen_notes.py 同惯例）。"""
import json


def test_parse_reply_basics():
    from scripts.gen_cues import parse_reply

    assert parse_reply('```json\n{"cue":"光呼吸的底物与产物"}\n```') == \
        {"cue": "光呼吸的底物与产物"}
    assert parse_reply('噪声 {"cue": "水势的组成"} 更多') == {"cue": "水势的组成"}
    assert parse_reply(json.dumps({"cue": "「气孔运动的机理」"}, ensure_ascii=False)) == \
        {"cue": "气孔运动的机理"}


def test_parse_reply_rejects_bad():
    from scripts.gen_cues import parse_reply

    assert parse_reply("") is None
    assert parse_reply("no json here") is None
    assert parse_reply(json.dumps({"cue": ""})) is None
    assert parse_reply(json.dumps({"cue": "单"})) is None
    assert parse_reply(json.dumps({"cue": "字" * 30})) is None
