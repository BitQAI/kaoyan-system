SAMPLE = """# 摘要

## 示例事件一

- 要点甲：一句话说明是什么。
- 要点乙：核心提法。
[考纲挂钩: 101-19 高质量发展]

## 示例事件二

- 要点丙：只列了一条。
"""


def _content():
    return {"subjects": [{"id": "101", "name": "思想政治理论", "has_content": True, "chapters": [
        {"id": "101-27", "name": "形势与政策", "weight_center": 5, "points": [
            {"id": "101-27-01", "text": "原有考点", "spoken": "原有考点", "tags": [],
             "listen_ok": True, "media": [], "audio": []},
            {"id": "101-27-ca01", "text": "旧时政——陈旧内容", "spoken": "旧", "tags": ["时政"],
             "listen_ok": True, "media": [], "audio": []},
        ], "listen": [{"src": "audio/101-27-c1.mp3", "dur": 20, "point_ids": ["101-27-01"]}],
         "quiz": [], "cards": []}]}]}


def test_parse_markdown_events_and_points():
    from scripts.apply_current_affairs import parse_markdown

    rows = parse_markdown(SAMPLE)
    assert [r["event"] for r in rows] == ["示例事件一", "示例事件一", "示例事件二"]
    assert rows[0]["point"].startswith("要点甲")
    assert all("考纲挂钩" not in r["point"] for r in rows)


def test_apply_rebuilds_points_idempotently():
    from scripts.apply_current_affairs import parse_markdown, apply_to_content

    content = _content()
    rows = parse_markdown(SAMPLE)
    stats = apply_to_content(content, rows)
    chap = content["subjects"][0]["chapters"][0]
    ids = [p["id"] for p in chap["points"]]
    assert stats == {"removed": 1, "added": 3}
    assert ids == ["101-27-01", "101-27-ca01", "101-27-ca02", "101-27-ca03"]
    assert chap["points"][1]["tags"] == ["时政", "高频"]
    assert "示例事件一" in chap["points"][1]["text"]
    assert chap["listen"] == []                    # 章级听单被清空待重生成

    # 幂等：再执行一次结果相同（数量不累积）
    stats2 = apply_to_content(content, rows)
    assert stats2 == {"removed": 3, "added": 3}
    assert [p["id"] for p in chap["points"]] == ids


def test_apply_keeps_non_ca_points():
    from scripts.apply_current_affairs import parse_markdown, apply_to_content

    content = _content()
    apply_to_content(content, parse_markdown(SAMPLE))
    chap = content["subjects"][0]["chapters"][0]
    assert any(p["id"] == "101-27-01" for p in chap["points"])
