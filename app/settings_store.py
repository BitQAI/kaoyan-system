import os
import pathlib

from app.config import ROOT

DEFAULTS = {"listen_minutes": 40, "look_n": 8, "quiz_n": 15, "voice": "Ethan", "rate": 1.0}


def load(con) -> dict:
    out = dict(DEFAULTS)
    for r in con.execute("SELECT k, v FROM settings"):
        if r["k"] in DEFAULTS:
            out[r["k"]] = type(DEFAULTS[r["k"]])(r["v"])
    return out


def save(con, patch: dict) -> dict:
    for k, v in patch.items():
        if k not in DEFAULTS:
            continue
        con.execute("INSERT INTO settings(k, v) VALUES(?,?) "
                    "ON CONFLICT(k) DO UPDATE SET v = excluded.v", (k, str(v)))
    con.commit()
    return load(con)


def env_file_path() -> pathlib.Path:
    return pathlib.Path(os.environ.get("KY_ENV_FILE") or (ROOT / ".env"))


def write_env_kv(key: str, value: str) -> None:
    p = env_file_path()
    lines = p.read_text(encoding="utf-8").splitlines() if p.exists() else []
    out, found = [], False
    for line in lines:
        if line.strip().startswith(key + "="):
            out.append(f"{key}={value}")
            found = True
        else:
            out.append(line)
    if not found:
        out.append(f"{key}={value}")
    p.write_text("\n".join(out) + "\n", encoding="utf-8")
