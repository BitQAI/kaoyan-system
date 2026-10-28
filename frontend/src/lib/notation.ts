/** 记号渲染：拉丁/希腊下标 → <sub>。原型没有这层，但 315 的化学式下标必须渲染才读得懂。
 *
 * 顺序：先把实测到的 42 个记号做精确映射，再用通用规则兜住新数据。
 * 通用规则 /([A-Za-zΔ])_([A-Za-z0-9]+)/ 不会误伤 SN1/SN2/E1/E2 —— 它们不含下划线。
 * 输入必须是已转义的文本（本模块只做记号替换，不做 HTML 转义）。
 */

const EXPLICIT: Record<string, string> = {
  "K_b": "K<sub>b</sub>",
  "c_B": "c<sub>B</sub>",
  "b_B": "b<sub>B</sub>",
  "E_a": "E<sub>a</sub>",
  "M_B": "M<sub>B</sub>",
  "x_T": "x<sub>T</sub>",
  "K_w": "K<sub>w</sub>",
  "K_f": "K<sub>f</sub>",
  "K_c": "K<sub>c</sub>",
  "K_p": "K<sub>p</sub>",
  "n_B": "n<sub>B</sub>",
  "T_f": "T<sub>f</sub>",
  "Q_p": "Q<sub>p</sub>",
  "x_B": "x<sub>B</sub>",
  "m_A": "m<sub>A</sub>",
  "Q_V": "Q<sub>V</sub>",
  "T_b": "T<sub>b</sub>",
  "n_g": "n<sub>g</sub>",
  "n_gRT": "n<sub>gRT</sub>",
  "p_B": "p<sub>B</sub>",
  "K_bn": "K<sub>bn</sub>",
  "V_A": "V<sub>A</sub>",
  "V_B": "V<sub>B</sub>",
  "c_x": "c<sub>x</sub>",
  "V_s": "V<sub>s</sub>",
  "V_x": "V<sub>x</sub>",
  "x_A": "x<sub>A</sub>",
  "m_B": "m<sub>B</sub>",
  "Q_r": "Q<sub>r</sub>",
  "E_r": "E<sub>r</sub>",
  "K_bc": "K<sub>bc</sub>",
  "c_HB": "c<sub>HB</sub>",
  "c_sp": "c<sub>sp</sub>",
  "a_Ox": "a<sub>Ox</sub>",
  "a_Red": "a<sub>Red</sub>",
  "c_s": "c<sub>s</sub>",
  "a_j": "a<sub>j</sub>",
  "S_EAr": "S<sub>EAr</sub>",
  "Ψw": "Ψ<sub>w</sub>",
  "Ψs": "Ψ<sub>s</sub>",
  "Ψp": "Ψ<sub>p</sub>",
  "Ψm": "Ψ<sub>m</sub>",
};

const explicitRe = new RegExp(
  "(" + Object.keys(EXPLICIT).sort((a, b) => b.length - a.length)
    .map((k) => k.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")).join("|") + ")",
  "g",
);

const DEFAULT_RE = /([A-Za-zΔ])_([A-Za-z0-9]+)/g;

export function notation(text: string): string {
  return text
    .replace(explicitRe, (m) => EXPLICIT[m] ?? m)
    .replace(DEFAULT_RE, "$1<sub>$2</sub>");
}

export const NOTATION_TOKENS = Object.keys(EXPLICIT);
