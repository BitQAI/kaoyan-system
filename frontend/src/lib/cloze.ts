/** 默写卡：按 `____` 切段，逐空比对答案。 */

export function parseCloze(question: string): string[] {
  return question.split("____");
}

function norm(s: string): string {
  return s
    .trim()
    .toLowerCase()
    .replace(/[.,!?;:'"()[\]{}]/g, "")
    .replace(/\s+/g, " ")
    .trim();
}

export function checkCloze(inputs: string[], answers: string[]): boolean[] {
  const n = Math.max(inputs.length, answers.length);
  const out: boolean[] = [];
  for (let i = 0; i < n; i += 1) {
    const a = answers[i];
    const b = inputs[i];
    out.push(a !== undefined && b !== undefined && norm(b) === norm(a));
  }
  return out;
}
