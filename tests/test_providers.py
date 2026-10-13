import json
import pathlib

FIXTURE = json.loads((pathlib.Path(__file__).parent / "fixtures" / "content_small.json").read_text())


def test_build_messages_includes_point_text():
    from app.services.providers import build_messages

    msgs = build_messages(("point", "812-04-01"), history=[], content=FIXTURE)
    assert msgs[0]["role"] == "system"
    assert "光合作用的意义" in msgs[0]["content"]


def test_build_messages_quiz_context():
    from app.services.providers import build_messages

    msgs = build_messages(("quiz", "q8120101"), history=[], content=FIXTURE)
    joined = " ".join(m["content"] for m in msgs)
    assert "细胞壁" in joined and "血红蛋白是动物蛋白" in joined


def test_build_messages_free_no_context():
    from app.services.providers import build_messages

    msgs = build_messages(("free", None), history=[{"role": "user", "content": "hi"}], content=FIXTURE)
    assert len(msgs) == 2


def test_stream_chat_parses_sse(monkeypatch):
    from app.services import providers

    class FakeResp:
        def raise_for_status(self):
            pass

        def iter_lines(self, decode_unicode=False):
            yield 'data: {"choices":[{"delta":{"reasoning_content":"想一下"}}]}'.encode()
            yield b""
            yield 'data: {"choices":[{"delta":{"content":"水势是"}}]}'.encode()
            yield 'data: {"choices":[{"delta":{"content":"化学势差。"}}]}'.encode()
            yield b"data: [DONE]"

    captured = {}

    def fake_post(url, headers=None, json=None, stream=None, timeout=None):
        captured.update({"url": url, "headers": headers, "json": json})
        return FakeResp()

    monkeypatch.setattr(providers.requests, "post", fake_post)

    class S:
        ai_provider = "opencode"
        opencode_key = "k"
        opencode_base = "https://opencode.ai/zen/go/v1"
        bailian_key = "b"
        bailian_base = ""

    events = list(providers.stream_chat([{"role": "user", "content": "q"}], "sess-1", S()))
    assert events == [
        {"type": "reasoning", "delta": "想一下"},
        {"type": "content", "delta": "水势是"},
        {"type": "content", "delta": "化学势差。"},
    ]
    assert captured["headers"]["x-opencode-session"] == "sess-1"
    assert captured["json"]["stream"] is True


def test_stream_chat_bailian_no_session_header(monkeypatch):
    from app.services import providers

    class FakeResp:
        def raise_for_status(self):
            pass

        def iter_lines(self, decode_unicode=False):
            yield 'data: {"choices":[{"delta":{"content":"ok"}}]}'.encode()
            yield b"data: [DONE]"

    captured = {}

    def fake_post(url, headers=None, json=None, stream=None, timeout=None):
        captured.update({"url": url, "headers": headers})
        return FakeResp()

    monkeypatch.setattr(providers.requests, "post", fake_post)

    class S:
        ai_provider = "bailian"
        opencode_key = ""
        opencode_base = ""
        bailian_key = "bk"
        bailian_base = "https://ws-x.cn-beijing.maas.aliyuncs.com/compatible-mode/v1"

    events = list(providers.stream_chat([{"role": "user", "content": "q"}], "sess-1", S()))
    assert events == [{"type": "content", "delta": "ok"}]
    assert "x-opencode-session" not in captured["headers"]
    assert captured["url"].endswith("/compatible-mode/v1/chat/completions")
