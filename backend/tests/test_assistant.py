import json

from app import assistant


def test_context_has_current_point(conn):
    text, related, refs = assistant.build_context(conn, "水势是什么", "8120001")
    assert related[0] == "8120001"
    assert "【当前知识点】" in text
    assert "【原文段落】" in text
    assert refs and refs[0].startswith("html:")


def test_context_includes_units_and_cards(conn):
    text, _, _ = assistant.build_context(conn, "讲讲", "8120001")
    assert "【记忆单元】" in text
    assert "【卡片】" in text


def test_context_respects_budget(conn):
    text, _, _ = assistant.build_context(conn, "讲讲", "8120001")
    assert len(text) < assistant.L1_BUDGET + assistant.L3_BUDGET + assistant.L4_BUDGET + 500


def test_context_without_point_still_recalls(conn):
    text, related, _ = assistant.build_context(conn, "光合作用", None)
    assert "【相关问题召回】" in text
    assert related


def test_syllabus_point_context_ok(conn):
    row = conn.execute(
        "SELECT id FROM point WHERE source_kind='syllabus' LIMIT 1").fetchone()
    text, _, _ = assistant.build_context(conn, "讲讲", row["id"])
    assert "【当前知识点】" in text


def test_persist_and_history(conn):
    cid = assistant.ensure_conversation(conn, None, "8120001", "水势是什么意思")
    assistant.persist_turn(conn, cid, "水势是什么意思", "它是水的化学势差……",
                           ["8120001"], ["html:p4-2"])
    items = assistant.history_for_point(conn, "8120001")
    assert items and items[0]["question"] == "水势是什么意思"
    assert items[0]["answer"].startswith("它是水")
    assert assistant.count_for_point(conn, "8120001") == 1


def test_history_matches_exact_id_only(conn):
    cid = assistant.ensure_conversation(conn, None, "2040101", "q")
    assistant.persist_turn(conn, cid, "q", "a", ["20401010"], [])
    assert assistant.history_for_point(conn, "2040101") == []


def test_conversation_listing_and_delete(conn):
    cid = assistant.ensure_conversation(conn, None, "8120002", "标题测试")
    assert any(c["id"] == cid for c in assistant.list_conversations(conn))
    assistant.delete_conversation(conn, cid)
    assert not any(c["id"] == cid for c in assistant.list_conversations(conn))


def test_context_includes_history(conn):
    cid = assistant.ensure_conversation(conn, None, "8120001", "第一问")
    assistant.persist_turn(conn, cid, "第一问", "第一答", ["8120001"], [])
    text, _, _ = assistant.build_context(conn, "再详细点", "8120001", cid)
    assert "【本次对话上文】" in text
    assert "第一答" in text


def test_sse_stream_and_persist(client, monkeypatch, conn):
    from app import ai

    async def fake_stream(question, context, history=None):
        for chunk in ("水势", "是水的", "化学势差。"):
            yield chunk

    monkeypatch.setattr(ai, "stream_answer", fake_stream)
    before = client.get("/api/assistant/history/count",
                        params={"point_id": "8120001"}).json()["count"]
    res = client.post("/api/assistant/ask",
                      json={"question": "水势是什么", "point_id": "8120001"})
    assert res.status_code == 200
    frames = [json.loads(line[6:]) for line in res.text.splitlines()
              if line.startswith("data: ")]
    assert [f["type"] for f in frames] == ["delta", "delta", "delta", "done"]
    assert "".join(f["delta"] for f in frames if f["type"] == "delta") == "水势是水的化学势差。"
    cid = frames[-1]["conversation_id"]
    msgs = json.loads(client.get(f"/api/assistant/conversations/{cid}").text)["messages"]
    assert len(msgs) == 2 and msgs[1]["content"] == "水势是水的化学势差。"
    after = client.get("/api/assistant/history/count",
                       params={"point_id": "8120001"}).json()["count"]
    assert after == before + 1


def test_ask_rejects_empty(client):
    assert client.post("/api/assistant/ask", json={"question": "  "}).status_code == 400
