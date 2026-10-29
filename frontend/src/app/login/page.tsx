"use client";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { postJson, setToken } from "@/lib/api";

export default function LoginPage() {
  const router = useRouter();
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [remember, setRemember] = useState(true);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    if (busy) return;
    setBusy(true);
    setError("");
    try {
      const res = await postJson<{ token: string; user: string }>("/api/auth/login", {
        username, password, remember,
      });
      setToken(res.token);
      router.replace("/study?view=study&sid=812");
    } catch (e) {
      setError(String(e).includes("401") ? "账号或密码不对" : "登录失败：" + String(e));
    } finally {
      setBusy(false);
    }
  }

  return (
    <main style={{ minHeight: "100vh", display: "grid", placeItems: "center", padding: 24 }}>
      <form
        onSubmit={submit}
        style={{
          width: "min(380px, 100%)", background: "var(--card)", border: "1px solid var(--line)",
          borderRadius: "var(--radius)", boxShadow: "var(--shadow)", padding: 26,
          backdropFilter: "blur(18px)",
        }}
      >
        <h1 style={{ fontSize: 21, margin: "0 0 4px" }}>考研 · 听学记</h1>
        <p className="muted" style={{ fontSize: 13, margin: "0 0 18px" }}>
          538 个知识点，随时提问
        </p>

        <label style={{ display: "block", fontSize: 12.5, color: "var(--muted)", marginBottom: 4 }}>
          账号
        </label>
        <input
          value={username}
          onChange={(e) => setUsername(e.target.value)}
          autoComplete="username"
          style={inputStyle}
        />
        <label style={{ display: "block", fontSize: 12.5, color: "var(--muted)", margin: "12px 0 4px" }}>
          密码
        </label>
        <input
          type="password"
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          autoComplete="current-password"
          style={inputStyle}
        />

        <label style={{ display: "flex", gap: 8, alignItems: "center", marginTop: 14, fontSize: 13.5 }}>
          <input type="checkbox" checked={remember} onChange={(e) => setRemember(e.target.checked)} />
          记住我（30 天内免登录）
        </label>

        {error && <p style={{ color: "var(--bad)", fontSize: 13, margin: "10px 0 0" }}>{error}</p>}

        <button className="btn primary" type="submit" disabled={busy}
          style={{ width: "100%", marginTop: 16, padding: "11px 0" }}>
          {busy ? "登录中…" : "登录"}
        </button>
      </form>
    </main>
  );
}

const inputStyle: React.CSSProperties = {
  width: "100%", padding: "10px 12px", borderRadius: 11, border: "1px solid var(--line)",
  background: "var(--bg2)", color: "var(--ink)", fontSize: 14, outline: "none",
};
