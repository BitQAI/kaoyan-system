"""LLM 供应商链 + 流式问答。

批量/离线生成优先 opencode 的 deepseek-v4.1-flash，失败再落 DeepSeek，
顺序由 LLM_PROVIDER_ORDER 决定，缺 key 的通道自动跳过。

opencode 通道两个坑（fk 项目实测，照搬注释）：
- 必须带 x-opencode-session 头，否则 400 MissingSessionID；
- 它是推理模型，max_tokens 会先被思考吃掉，给太小返回空串，
  因此抬到 OPENCODE_MIN_MAX_TOKENS，并把空串当失败继续回落。
"""
import json
from dataclasses import dataclass
from functools import lru_cache

from openai import AsyncOpenAI, OpenAI

from app import config

#: 默认回答预算：约合 500–600 个中文字符，给「结论 + 3 个要点」留足余量
STREAM_MAX_TOKENS = 800

SYSTEM_PROMPT = """你是考研辅导老师。学生已经在手机上读过知识点原文，没读懂才来问。只解决他这个问题，不复述、不铺垫。

结构（严格遵守）：
1. 第一行直接给结论：一句人话，≤30 字，加粗。
2. 之后最多 3 个要点，每行以「- 」开头，每点 ≤50 字，只写原因、区别、记忆抓手、易错点这类有用信息。
3. 只有需要落到考试时才写最后一行「考场：……」，≤40 字；不需要就不写。

长度：一般问题全文 150–250 字。只有当学生明确说「展开」「细讲」「多说一点」时，才允许写到 500 字；展开时也最多 5 个要点、每点 ≤60 字，仍然只写与问题直接相关的信息。

不要写：
- 不复述学生的问题；不写「这个问题问得好」之类的开场白，不写「希望对你有帮助」之类的结尾。
- 不用 Markdown 小标题、表格、emoji；不把同一句话换个说法再说一遍。
- 不摊开与问题无关的完整知识体系。

补充与事实：
- 资料没覆盖、但确实需要交代的背景，另起一行用「补充：」开头。
- 提供的资料是权威口径，与资料冲突时以资料为准。
- 不得编造考纲条款或条款号。资料里 exam_evidence.level 为 inferred 的，说「这是推断」，不说「考纲要求」。
- 不确定就直说不知道，不要圆场。"""


@dataclass(frozen=True)
class Provider:
    name: str
    api_key: str
    base_url: str
    model: str
    min_max_tokens: int = 0
    session_header: bool = False


def provider_chain() -> list[Provider]:
    known = {
        "opencode": lambda: Provider(
            "opencode", config.OPENCODE_API_KEY, config.OPENCODE_BASE_URL,
            config.OPENCODE_MODEL, config.OPENCODE_MIN_MAX_TOKENS, True),
        "deepseek": lambda: Provider(
            "deepseek", config.DEEPSEEK_API_KEY, config.DEEPSEEK_BASE_URL,
            config.DEEPSEEK_MODEL),
    }
    out = []
    for name in config.LLM_PROVIDER_ORDER:
        build = known.get(name)
        if build is None:
            continue
        provider = build()
        if provider.api_key:
            out.append(provider)
    return out


#: 最近一次成功命中的供应商（排障用）
_last_provider: str | None = None


def provider_status() -> dict:
    return {"order": [p.name for p in provider_chain()],
            "last_used": _last_provider,
            "chat_provider": config.LLM_CHAT_PROVIDER}


@lru_cache(maxsize=8)
def _client(api_key: str, base_url: str) -> OpenAI:
    return OpenAI(api_key=api_key, base_url=base_url)


def call_llm(system: str, user: str, temperature: float = 0.3,
             max_tokens: int = 1200) -> str | None:
    """按供应商链调用；空响应与异常都视为失败并落到下一家。"""
    global _last_provider
    for provider in provider_chain():
        kwargs = {"model": provider.model,
                  "messages": [{"role": "system", "content": system},
                               {"role": "user", "content": user}],
                  "temperature": temperature,
                  "max_tokens": max(int(max_tokens), provider.min_max_tokens)}
        if provider.session_header:
            kwargs["extra_headers"] = {"x-opencode-session": config.OPENCODE_SESSION}
        try:
            resp = _client(provider.api_key,
                           provider.base_url).chat.completions.create(**kwargs)
            content = resp.choices[0].message.content
        except Exception:  # noqa: BLE001 - 网络/限流一律兜底
            continue
        if content and content.strip():
            _last_provider = provider.name
            return content
    return None


def chat_target() -> tuple[AsyncOpenAI | None, str, dict]:
    """流式问答的（客户端, 模型名, 额外请求头）。"""
    if config.LLM_CHAT_PROVIDER == "opencode" and config.OPENCODE_API_KEY:
        return (AsyncOpenAI(api_key=config.OPENCODE_API_KEY,
                            base_url=config.OPENCODE_BASE_URL),
                config.OPENCODE_MODEL,
                {"x-opencode-session": config.OPENCODE_SESSION})
    if not config.DEEPSEEK_API_KEY:
        return None, "", {}
    return (AsyncOpenAI(api_key=config.DEEPSEEK_API_KEY,
                        base_url=config.DEEPSEEK_BASE_URL),
            config.DEEPSEEK_MODEL, {})


async def stream_answer(question: str, context_text: str,
                        history: list[dict] | None = None):
    client, model, extra = chat_target()
    if client is None:
        yield "AI 助手未配置 LLM 密钥，请先在仓库根 .env 里填写 DEEPSEEK_API_KEY。"
        return
    messages = [{"role": "system", "content": SYSTEM_PROMPT}]
    for msg in history or []:
        messages.append({"role": msg["role"], "content": msg["content"]})
    messages.append({"role": "user",
                     "content": f"参考资料：\n{context_text}\n\n问题：{question}"})
    max_tokens = STREAM_MAX_TOKENS
    if config.LLM_CHAT_PROVIDER == "opencode" and config.OPENCODE_API_KEY:
        # 推理模型的思考也占预算，给太小会返回空串
        max_tokens = max(max_tokens, config.OPENCODE_MIN_MAX_TOKENS)
    try:
        stream = await client.chat.completions.create(
            model=model, messages=messages, stream=True, temperature=0.4,
            max_tokens=max_tokens, extra_headers=extra or None,
        )
        async for chunk in stream:
            delta = chunk.choices[0].delta.content
            if delta:
                yield delta
    except Exception:  # noqa: BLE001
        yield "\n\n（AI 服务暂时不可用，请稍后重试；看、记、听不受影响。）"
