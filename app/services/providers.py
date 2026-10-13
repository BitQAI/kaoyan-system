import json
from typing import Iterator

import requests

MODEL = "deepseek-v4.1-flash"

SYSTEM_PROMPT = (
    "你是考研辅导助教，面向备战 2027 考研的学生，重点科目为 315 化学（农）与 812 植物生理学。"
    "回答要求：先给结论，再分点展开；按考试答题语言组织；涉及机制时写清因果链；"
    "无法确定的内容明确说明「请对照教材核验」，不要编造。"
)


def build_messages(owner, history: list[dict], content: dict) -> list[dict]:
    from app import content as content_mod

    owner_type, owner_ref = owner
    parts = [SYSTEM_PROMPT]
    if owner_type == "point" and owner_ref:
        found = content_mod.find_point(content, owner_ref)
        if found:
            _, chap, p = found
            parts.append(f"当前知识点：{p.get('text', '')}\n所属章节：{chap.get('name', '')}")
            if p.get("spoken"):
                parts.append(f"该点的朗读版（供口语化参考）：{p['spoken']}")
    elif owner_type == "quiz" and owner_ref:
        found = content_mod.find_quiz(content, owner_ref)
        if found:
            _, _, q = found
            options = "\n".join(f"{chr(65+i)}. {o}" for i, o in enumerate(q.get("options", [])))
            parts.append(f"当前题目：{q.get('stem', '')}\n{options}\n"
                         f"正确答案：{chr(65 + q['answer'])}\n解析：{q.get('explain', '')}")
    msgs = [{"role": "system", "content": "\n\n".join(parts)}]
    msgs.extend(history[-10:])
    return msgs


def stream_chat(messages: list[dict], session_id: str, settings, timeout: int = 120) -> Iterator[dict]:
    if settings.ai_provider == "bailian":
        url = settings.bailian_base.rstrip("/") + "/chat/completions"
        headers = {"Authorization": f"Bearer {settings.bailian_key}"}
    else:
        url = settings.opencode_base.rstrip("/") + "/chat/completions"
        headers = {"Authorization": f"Bearer {settings.opencode_key}",
                   "x-opencode-session": session_id}
    resp = requests.post(
        url,
        headers={**headers, "Content-Type": "application/json"},
        json={"model": MODEL, "messages": messages, "stream": True, "max_tokens": 2048},
        stream=True,
        timeout=timeout,
    )
    resp.raise_for_status()
    for raw in resp.iter_lines(decode_unicode=False):
        # SSE 响应常无 charset，requests 会按 latin-1 解码破坏中文；这里显式 UTF-8
        line = raw.decode("utf-8", errors="replace")
        if not line or not line.startswith("data:"):
            continue
        payload = line[5:].strip()
        if payload == "[DONE]":
            break
        try:
            obj = json.loads(payload)
        except json.JSONDecodeError:
            continue
        choices = obj.get("choices") or [{}]
        delta = choices[0].get("delta") or {}
        if delta.get("reasoning_content"):
            yield {"type": "reasoning", "delta": delta["reasoning_content"]}
        if delta.get("content"):
            yield {"type": "content", "delta": delta["content"]}
