// 词汇与作文复习流程的端到端检查。
//   node --experimental-strip-types frontend/e2e/vocab.mjs --unit         只跑纯函数断言
//   KY_USER=kaoyan KY_PASS=*** node frontend/e2e/vocab.mjs [baseUrl]      浏览器流程
import assert from "node:assert/strict";

if (process.argv.includes("--unit")) {
  const { parseCloze, checkCloze } = await import("../src/lib/cloze.ts");

  assert.deepEqual(parseCloze("a ____ b ____ c"), ["a ", " b ", " c"]);
  assert.deepEqual(parseCloze("no blank"), ["no blank"]);
  assert.equal(parseCloze("____").length, 2);

  assert.deepEqual(checkCloze(["Expect"], ["expect"]), [true]);
  assert.deepEqual(checkCloze([" grow "], ["growth"]), [false]);
  assert.deepEqual(checkCloze(["grow!"], ["grow"]), [true]);
  assert.deepEqual(checkCloze(["expect"], ["expect", "growth"]), [true, false]);
  assert.deepEqual(checkCloze(["expect", "x"], ["expect"]), [true, false]);

  console.log("cloze unit ok");
  process.exit(0);
}

const BASE = process.argv[2] || "http://localhost:3000";
const USER = process.env.KY_USER;
const PASS = process.env.KY_PASS;
const TOKEN = process.env.KY_TOKEN;
if (!TOKEN && (!USER || !PASS)) {
  console.error("需要 KY_USER/KY_PASS 或 KY_TOKEN");
  process.exit(2);
}

const { chromium } = await import("playwright");
const EXECUTABLE = process.env.PW_EXECUTABLE ||
  `${process.env.HOME}/Library/Caches/ms-playwright/chromium_headless_shell-1234/chrome-headless-shell-mac-arm64/chrome-headless-shell`;

let failed = 0;
function check(name, ok, detail = "") {
  if (!ok) failed += 1;
  console.log(`${ok ? "✓" : "✗"} ${name}${detail ? " — " + detail : ""}`);
}

const browser = await chromium.launch({ executablePath: EXECUTABLE });
const page = await browser.newPage({ viewport: { width: 420, height: 860 } });
const errors = [];
page.on("pageerror", (e) => errors.push(String(e)));

if (TOKEN) {
  await page.goto(`${BASE}/login`, { waitUntil: "domcontentloaded" });
  await page.evaluate((t) => localStorage.setItem("kaoyan.auth.token", t), TOKEN);
} else {
  await page.goto(`${BASE}/login`, { waitUntil: "networkidle" });
  await page.fill('input[name="username"], input[type="text"]', USER);
  await page.fill('input[type="password"]', PASS);
  await page.keyboard.press("Enter");
  await page.waitForLoadState("networkidle");
}

// 词汇：翻面看释义与真题标注
await page.goto(`${BASE}/study?view=memo&sid=204`, { waitUntil: "networkidle" });
await page.evaluate(() => {
  localStorage.setItem("kaoyan.scope.v1.204", JSON.stringify({ chapters: ["204-10"], limit: 20 }));
});
await page.reload({ waitUntil: "networkidle" });
await page.waitForSelector(".word-title", { timeout: 15000 });
check("词卡正面渲染", true);
await page.click(".flip-btn.primary");
await page.waitForSelector(".word-senses", { timeout: 8000 });
const back = await page.textContent(".flip-back");
check("翻面有释义", /[a-zA-Z]/.test(back || ""));
check("真题标注存在", /真题|非真题原句/.test(back || ""));

// 作文：整篇朗读卡
await page.evaluate(() => {
  localStorage.setItem("kaoyan.scope.v1.204", JSON.stringify({ chapters: ["204-08"], limit: 20 }));
});
await page.reload({ waitUntil: "networkidle" });
await page.waitForSelector(".question", { timeout: 15000 });
const q = await page.textContent(".flip-front .question");
check("范文整篇卡出现", /整篇朗读/.test(q || ""), q?.slice(0, 24));

check("无前端报错", errors.length === 0, errors.slice(0, 2).join(" | "));

await browser.close();
console.log(failed === 0 ? "vocab e2e ok" : `vocab e2e failed: ${failed}`);
process.exit(failed === 0 ? 0 : 1);
