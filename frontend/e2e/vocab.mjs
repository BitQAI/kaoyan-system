// 词汇与作文卡片的检查脚本。
//   node --experimental-strip-types frontend/e2e/vocab.mjs --unit   只跑纯函数断言
//   KY_USER=... KY_PASS=... node frontend/e2e/vocab.mjs [baseUrl]   浏览器流程（Task 13 补齐）
import assert from "node:assert/strict";

if (process.argv.includes("--unit")) {
  const { parseCloze, checkCloze } = await import("../src/lib/cloze.ts");

  assert.deepEqual(parseCloze("a ____ b ____ c"), ["a ", " b ", " c"]);
  assert.deepEqual(parseCloze("no blank"), ["no blank"]);
  assert.equal(parseCloze("____").length, 2);

  assert.deepEqual(checkCloze(["Expect"], ["expect"]), [true]);
  assert.deepEqual(checkCloze([" grow "], ["growth"]), [false]);
  assert.deepEqual(checkCloze(["grow!"], ["grow"]), [true]);
  // 输入少于答案：缺的项按错算，不抛异常
  assert.deepEqual(checkCloze(["expect"], ["expect", "growth"]), [true, false]);
  // 输入多于答案：多出的项按错算
  assert.deepEqual(checkCloze(["expect", "x"], ["expect"]), [true, false]);

  console.log("cloze unit ok");
  process.exit(0);
}

console.log("browser flow lands in Task 13");
