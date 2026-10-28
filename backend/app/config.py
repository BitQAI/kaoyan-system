"""路径与环境变量唯一入口。

.env 位于仓库根，只保存密钥类配置，不入库。
"""
import os
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent.parent
ROOT_DIR = BACKEND_DIR.parent
ENV_PATH = ROOT_DIR / ".env"


def _load_dotenv(path: Path) -> None:
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        os.environ.setdefault(key.strip(), value.strip())


_load_dotenv(ENV_PATH)

DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY", "")
DEEPSEEK_BASE_URL = os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com")
DEEPSEEK_MODEL = os.getenv("DEEPSEEK_MODEL", "deepseek-chat")

# opencode zen 通道（deepseek-v4.1-flash，推理模型）：批量生成优先，失败回落 DeepSeek
OPENCODE_API_KEY = os.getenv("OPENCODE_API_KEY", "")
OPENCODE_BASE_URL = os.getenv("OPENCODE_BASE_URL", "https://opencode.ai/zen/go/v1")
OPENCODE_MODEL = os.getenv("OPENCODE_MODEL", "deepseek-v4.1-flash")
#: 该通道要求带 x-opencode-session 头，缺了会 400 MissingSessionID
OPENCODE_SESSION = os.getenv("OPENCODE_SESSION", "kaoyan-study")
#: 推理模型先把预算花在思考上，给太小会返回空串，这里设下限
OPENCODE_MIN_MAX_TOKENS = int(os.getenv("OPENCODE_MIN_MAX_TOKENS", "1600"))
#: 供应商顺序（只启用配置了 key 的）
LLM_PROVIDER_ORDER = [p.strip() for p in os.getenv(
    "LLM_PROVIDER_ORDER", "opencode,deepseek").split(",") if p.strip()]
#: 交互式流式问答默认走 DeepSeek：opencode 是推理模型，首字延迟明显更高
LLM_CHAT_PROVIDER = os.getenv("LLM_CHAT_PROVIDER", "deepseek")

DATA_DIR = Path(os.getenv("KY_DATA_DIR", str(ROOT_DIR / "data")))
DB_PATH = Path(os.getenv("KY_DB", str(DATA_DIR / "ky.db")))
META_DIR = Path(os.getenv("KY_META_DIR", str(ROOT_DIR / "知识点元数据")))
SUBJECTS = ("812", "315", "101", "204")
EXAM_DATE = os.getenv("KY_EXAM_DATE", "2026-12-19")


def ai_configured() -> bool:
    return bool(DEEPSEEK_API_KEY or OPENCODE_API_KEY)
