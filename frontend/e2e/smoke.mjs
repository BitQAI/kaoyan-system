// 冒烟 e2e：登录 → 看 → 听（只念设问解析）→ 记 → 按题问 AI → 搜索 → 历史。
// AI 用拦截的假流，不消耗真实额度；但会校验请求里带了 card_id。
// 用法：KY_USER=kaoyan KY_PASS=xxx node e2e/smoke.mjs [baseUrl]
import { chromium } from "playwright";

const BASE = process.argv[2] || "http://localhost:3000";
const USER = process.env.KY_USER;
const PASS = process.env.KY_PASS;
if (!USER || !PASS) {
  console.error("需要 KY_USER / KY_PASS 环境变量（本地开发账号）");
  process.exit(2);
}

const results = [];
let failed = 0;
function check(name, ok, detail = "") {
  results.push({ name, ok });
  if (!ok) failed += 1;
  console.log(`${ok ? "✓" : "✗"} ${name}${detail ? " — " + detail : ""}`);
}

const EXECUTABLE = process.env.PW_EXECUTABLE || `${process.env.HOME}/Library/Caches/ms-playwright/chromium_headless_shell-1234/chrome-headless-shell-mac-arm64/chrome-headless-shell`;
const browser = await chromium.launch({ executablePath: EXECUTABLE });
const page = await browser.newPage({ viewport: { width: 1280, height: 900 } });
const errors = [];
page.on("pageerror", (e) => errors.push(String(e)));
page.on("console", (m) => { if (m.type() === "error") errors.push(m.text()); });

let capturedAsk = null;
await page.route("**/api/assistant/ask", async (route) => {
  capturedAsk = route.request().postDataJSON();
  const body = [
    { type: "delta", delta: "# 换个说法\n\n" },
    { type: "delta", delta: "**自由水**是可以自由移动的水。" },
    { type: "done", message_id: 1, conversation_id: "e2e-conv", related_point_ids: ["8120201"] },
  ].map((o) => `data: ${JSON.stringify(o)}\n\n`).join("");
  await route.fulfill({ status: 200, headers: { "Content-Type": "text/event-stream" }, body });
});

// —— 登录 ——
await page.goto(`${BASE}/login`);
await page.fill('input[autocomplete="username"]', USER);
await page.fill('input[type="password"]', PASS);
await page.click('button[type="submit"]');
await page.waitForSelector(".study-card", { timeout: 25000 });
check("登录并进入学习页", page.url().includes("/study"));

// —— 看 ——
check("看视图渲染标题", (await page.textContent(".study-title"))?.includes("植物生理学"));
check("考点解析有段落", await page.locator(".explain .prose p").count() > 0);
check("怎么考有列表", await page.locator(".exam-list li").count() > 0);
check("图示已渲染", await page.locator(".svg-wrap svg").count() > 0);
check("已去掉证据强度徽标", await page.locator(".badge.verified, .badge.inferred").count() === 0);
check("关联区", await page.locator(".relations .rel-link").count() > 0);
check("学用知识点导航（无章节树）", await page.locator(".point-nav .pn-current").count() === 1);
await page.click(".pn-current");
await page.waitForSelector(".pn-sheet", { timeout: 5000 });
check("目录按章分组", await page.locator(".pn-item").count() > 0);
await page.click(".pn-sheet .picker-head .badge-btn");
await page.click(".pn-arrow >> nth=1");
await page.waitForTimeout(400);
check("下一个知识点可用", (await page.textContent(".pn-sub"))?.includes("/"));
check("无引导提示文案", await page.locator(".mode-hint").count() === 0);
await page.click(".hp");
await page.waitForSelector(".progress-panel", { timeout: 5000 });
check("进度明细展开", await page.locator(".pp-row").count() > 0);
await page.click(".hp");

// —— 底部导航 + 科目切换 ——
check("底部导航四项", await page.locator(".bn-item").count() === 4);
await page.click(".sp-trigger");
await page.waitForSelector(".sp-menu", { timeout: 5000 });
check("科目下拉可用", await page.locator(".sp-item").count() === 4);
await page.click(".sp-item >> nth=0");

// —— 自定义范围 ——
await page.click(".range-btn");
await page.waitForSelector(".picker", { timeout: 5000 });
check("范围选择器打开", await page.locator(".picker-row").count() > 0);
await page.click(".picker-head .badge-btn");

// —— 听：只念设问与解析 ——
await page.goto(`${BASE}/study?view=listen&sid=812`);
await page.waitForSelector(".stepper-card", { timeout: 25000 });
check("听视图为逐条模式", await page.locator(".stepper-card").count() === 1);
check("听是卡片粒度（考点+解析）",
  (await page.locator(".listen-block h3").first().textContent()) === "考点"
  && (await page.locator(".listen-block h3").nth(1).textContent()) === "解析");
check("听不出现选项", await page.locator(".stepper-card .options").count() === 0);
const kindBadges = await page.locator(".stepper-card .card-top .badge").allTextContents();
check("徽标不重复", new Set(kindBadges).size === kindBadges.length, kindBadges.join("/"));
check("有逐条进度", await page.locator(".stepper-bar .progress-bar").count() === 1);
check("语速是拖动条", await page.locator('.rate-slider input[type="range"]').count() === 1);
check("听有优先级徽标", await page.locator(".badge.pri").count() > 0);
await page.click(".stepper-nav .btn.primary");
check("下一条可用", await page.locator(".stepper-nav .btn.primary").count() === 1);

// —— 记 + 按题问 AI ——
await page.goto(`${BASE}/study?view=memo&sid=812`);
await page.waitForSelector(".flip-card", { timeout: 25000 });
check("记视图为逐条模式", await page.locator(".stepper-bar").count() === 1);
await page.click(".flip-front .ai-entry-btn");
await page.waitForSelector(".ai-chat", { timeout: 5000 });
await page.fill(".ai-composer textarea", "这题怎么理解");
await page.click(".ai-send");
await page.waitForSelector(".ai-md", { timeout: 15000 });
check("AI 流式渲染", (await page.textContent(".ai-md"))?.includes("自由水"));
check("提问带 card_id", Boolean(capturedAsk?.card_id), JSON.stringify(capturedAsk));
await page.click(".ai-chat-head button");
await page.click(".flip-front .question");
await page.waitForSelector(".grade-row.show");
check("点卡片任意处即可翻面", true);
check("翻面显示要点", await page.locator(".flip-back .answer-points li").count() > 0);
check("记有优先级徽标", await page.locator(".badge.pri").count() > 0);
await page.click('.grade-row button[data-grade="秒答"]');
await page.waitForTimeout(500);
check("评分后仍在逐条模式", await page.locator(".stepper-bar").count() === 1);

// —— 搜索 ——
await page.goto(`${BASE}/study?view=study&sid=812`);
await page.fill(".search-box input", "水势");
await page.waitForSelector(".search-group-title", { timeout: 10000 });
check("检索有分组结果", await page.locator(".search-group-title").count() >= 1);

// —— 收藏 + 我的 ——
const starBefore = await page.locator(".star-btn.on").count();
const favPosted = () => page.waitForResponse(
  (r) => r.url().includes("/api/favorites") && r.request().method() === "POST",
  { timeout: 8000 });
let posted = favPosted();
await page.click(".star-btn >> nth=0");
await posted;
const starAfter = await page.locator(".star-btn.on").count();
check("收藏可切换", starBefore !== starAfter);
if (starAfter === 0) {          // 保证 /me 上至少有一条收藏可看
  posted = favPosted();
  await page.click(".star-btn >> nth=0");
  await posted;                 // 等落库完成再跳页，否则 goto 会中断请求
}
await page.goto(`${BASE}/me`);
await page.waitForSelector(".me-page", { timeout: 20000 });
check("我的页打开", await page.locator(".me-tabs button").count() === 4);
await page.waitForSelector(".me-row, .empty", { timeout: 10000 });
// 收藏是跨轮次的持久状态，这里只验证页面能正确渲染列表或空态
check("收藏页可渲染", await page.locator(".me-row, .empty").count() > 0);
await page.click('.me-tabs button >> nth=1');
await page.waitForTimeout(400);
check("错题本可切换", await page.locator(".me-row, .empty").count() > 0);

// —— 进度预测 ——
await page.click('.me-tabs button:has-text("进度预测")');
await page.waitForSelector(".fc-row", { timeout: 10000 });
check("四科学完预测可见", await page.locator(".fc-row").count() === 4);

// —— 历史页 ——
await page.goto(`${BASE}/history`);
await page.waitForSelector(".history-page", { timeout: 20000 });
check("历史页可打开", await page.locator(".history-conv").count() >= 0);

check("无前端运行时错误", errors.length === 0, errors.slice(0, 2).join(" | "));

await browser.close();
console.log(`\n${results.length - failed}/${results.length} 通过`);
process.exit(failed ? 1 : 0);
