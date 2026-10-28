// 冒烟 e2e：看 → 问 AI → 记 → 看历史 → 搜索。AI 用拦截的假流，不消耗真实额度。
// 用法：node e2e/smoke.mjs [baseUrl]
import { chromium } from "playwright";

const BASE = process.argv[2] || "http://localhost:3000";
const results = [];
let failed = 0;

function check(name, ok, detail = "") {
  results.push({ name, ok, detail });
  if (!ok) failed += 1;
  console.log(`${ok ? "✓" : "✗"} ${name}${detail ? " — " + detail : ""}`);
}

// 用本机已缓存的 headless shell，避免联网下载；可用 PW_EXECUTABLE 覆盖
const EXECUTABLE = process.env.PW_EXECUTABLE || `${process.env.HOME}/Library/Caches/ms-playwright/chromium_headless_shell-1234/chrome-headless-shell-mac-arm64/chrome-headless-shell`;
const browser = await chromium.launch({ executablePath: EXECUTABLE });
const page = await browser.newPage({ viewport: { width: 1280, height: 900 } });
const errors = [];
page.on("pageerror", (e) => errors.push(String(e)));
page.on("console", (m) => { if (m.type() === "error") errors.push(m.text()); });

// 假 AI 流：delta ×3 + done
await page.route("**/api/assistant/ask", async (route) => {
  const body = [
    { type: "delta", delta: "# 换个说法\n\n" },
    { type: "delta", delta: "**水势**就是水的" },
    { type: "delta", delta: "化学势差。\n" },
    { type: "done", message_id: 1, conversation_id: "e2e-conv", related_point_ids: ["8120001"] },
  ].map((o) => `data: ${JSON.stringify(o)}\n\n`).join("");
  await route.fulfill({
    status: 200,
    headers: { "Content-Type": "text/event-stream" },
    body,
  });
});

// —— 看 ——
await page.goto(`${BASE}/study?view=study&sid=812&pid=8120001`);
await page.waitForSelector(".study-title", { timeout: 20000 });
check("看视图渲染标题", (await page.textContent(".study-title"))?.includes("植物生理学"));
check("考点解析有段落", await page.locator(".explain .prose p").count() > 0);
check("怎么考有列表", await page.locator(".exam-list li").count() > 0);
check("图示已渲染", await page.locator(".svg-wrap svg").count() > 0);
check("证据徽章", await page.locator(".badge.verified, .badge.inferred").count() > 0);
check("关联区", await page.locator(".relations .rel-link").count() > 0);

// —— 问 AI ——
await page.click(".study-card .ai-entry-btn");
await page.waitForSelector(".ai-chat");
check("问 AI 面板打开", await page.isVisible(".ai-chat"));
check("自动带入当前知识点", (await page.inputValue(".ai-composer textarea")).includes("植物生理学"));
await page.click(".ai-send");
await page.waitForSelector(".ai-md", { timeout: 15000 });
const answer = await page.textContent(".ai-md");
check("流式回答渲染", (answer ?? "").includes("化学势差"), answer?.slice(0, 40));

// —— 记 ——
await page.goto(`${BASE}/study?view=memo&sid=812`);
await page.waitForSelector(".flip-card", { timeout: 20000 });
const firstQ = await page.textContent(".flip-front .question");
await page.click(".flip-front .flip-btn");
await page.waitForSelector(".grade-row.show");
check("翻面显示要点", await page.locator(".flip-back .answer-points li").count() > 0);
await page.click('.grade-row button[data-grade="秒答"]');
await page.waitForTimeout(600);
const nextQ = await page.textContent(".flip-front .question");
check("评分后进入下一张", nextQ !== firstQ);

// —— 听 ——
await page.goto(`${BASE}/study?view=listen&sid=812`);
await page.waitForSelector(".q-card", { timeout: 20000 });
check("听队列有卡片", await page.locator(".q-card").count() > 0);
check("朗读稿可展开", await page.locator(".q-card .script summary").count() > 0);
await page.click(".q-card .script summary");
check("朗读稿分块渲染", await page.locator(".script-block").count() > 0);

// —— 搜索 ——
await page.goto(`${BASE}/study?view=study&sid=812`);
await page.fill(".search-box input", "水势");
await page.waitForSelector(".search-group-title", { timeout: 10000 });
check("检索有分组结果", await page.locator(".search-group-title").count() >= 1);

// —— 历史页 ——
await page.goto(`${BASE}/history`);
await page.waitForSelector(".history-page", { timeout: 20000 });
check("历史页可打开", await page.locator("body").count() === 1);

check("无前端运行时错误", errors.length === 0, errors.slice(0, 2).join(" | "));

await browser.close();
console.log(`\n${results.length - failed}/${results.length} 通过`);
process.exit(failed ? 1 : 0);
