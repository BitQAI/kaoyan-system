"""三题型判分：single（下标）/ multi（集合全对）/ blank（归一化匹配 accept）。"""

_MAP = str.maketrans({
    "×": "*", "·": "*", "✕": "*", "✖": "*", "x": "*", "X": "*",
    "－": "-", "−": "-", "–": "-", "—": "-", "⁻": "-", "₋": "-",
    "＋": "+", "⁺": "+",
    "^": "",
    "⁰": "0", "¹": "1", "²": "2", "³": "3", "⁴": "4",
    "⁵": "5", "⁶": "6", "⁷": "7", "⁸": "8", "⁹": "9",
    "₀": "0", "₁": "1", "₂": "2", "₃": "3", "₄": "4",
    "₅": "5", "₆": "6", "₇": "7", "₈": "8", "₉": "9",
    "（": "(", "）": ")", "，": ",", "、": ",", "。": ".",
})


def normalize_blank(s: str) -> str:
    s = "".join(ch for ch in (s or "") if not ch.isspace())
    return s.translate(_MAP).lower()


def grade(quiz: dict, response) -> dict:
    """返回 {"correct": bool, "answer": 原样答案（供解析展示）}。"""
    t = quiz.get("type", "single")
    if t == "multi":
        ans = set(quiz["answer"])
        got = set(response or [])
        return {"correct": got == ans, "answer": quiz["answer"]}
    if t == "blank":
        blanks = quiz["blanks"]
        inputs = [normalize_blank(x) for x in (response or [])]
        ok = len(inputs) == len(blanks) and all(
            any(inp == normalize_blank(a) for a in b.get("accept", []))
            for inp, b in zip(inputs, blanks))
        return {"correct": ok, "answer": [b["accept"][0] for b in blanks]}
    return {"correct": response == quiz["answer"], "answer": quiz["answer"]}
