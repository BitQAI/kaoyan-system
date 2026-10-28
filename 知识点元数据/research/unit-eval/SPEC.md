# 未成卡 unit 评估规范

## 输入

`batches/<批次>.json`：
```json
{"subject": "315", "units": [
  {"point_id": "3151405", "idx": 6, "unit": "该 unit 原文",
   "title": "点位标题", "point": "点位全文", "exam": "考法说明",
   "units_all": ["本点全部 unit…"], "cards": [{"kind","question","answer"}, …]}
]}
```

`units_all` + `cards` 是判定的全部依据：先看本点已有卡片覆盖到什么，再判断这条 unit 是否已被覆盖。

## 输出

`out/<批次>.jsonl`，每条 unit 一行，JSON 字段固定为：
```json
{"point_id","idx","unit","verdict","reason","target","suggestion"}
```
- `verdict` ∈ `skip` / `merge` / `new_card`
- `unit` 必须与输入逐字一致（便于回查）
- 行序与输入 `units` 顺序一致；每批次覆盖该文件内全部 unit，不多不少

## 三档判定

**skip** — 满足任一：
- 已被本点某张卡完整覆盖（reason 里点名是哪张卡）
- 非知识点：框架过渡、答题策略提示、纯推导背景、教材行文
- 与本点主旨重复但与任何卡都不构成补充

**merge** — 实质是某个已有卡的补充要点，单独成卡会碎片化：
- `target` 填目标卡的 `question` 原文（必须能在 `cards` 里精确匹配到）
- `suggestion` 留 `{}`
- reason 写明「补入什么」

**new_card** — 独立可考、现有卡未覆盖：
- `suggestion` = `{"kind","card_type","question","answer"}`
- `kind` 必须取自本科目已有取值：
  - 812：`名解` / `简答` / `论述`
  - 315：`选择` / `填空` / `分析` / `计算` / `合成`
  - 101：`简答` / `名词解释` / `分析`
  - 204：`技巧` / `模板` / `句型` / `词汇`
- `card_type` 取自九类：`定义/原理/条件/公式/过程/辨析/应用/易错/记忆`
- `question` 与 `answer` 必须成对给出，answer 要是可直接背诵的作答要点（不是"见教材"）
- 判断题先问自己：这条若单独成卡，考生背它能否直接得分？不能则降为 merge 或 skip

## 硬约束

- **不臆造真题、不编考频**。`exam` 字段没写的，不得在 reason 中声称"高频/必考"；只能就知识结构说"独立可考"。
- **不改任何数据文件**。只写 `out/<批次>.jsonl`。
- 卡片 fragment 只在已覆盖/未覆盖之间判断，不重写已有卡。
- 得分点导向：优先识别「一词之差就失分」的区分点（名词辨析、条件、单位、方向），其次才是成段的论述素材。

## 自检（交付前必跑）

1. 行数 = 输入 unit 数
2. `unit` 字段与输入逐字一致，条数一致，无重复 `(point_id, idx)`
3. `verdict` 三值之外为 0
4. `merge` 的 `target` 必须在该点 `cards[].question` 中精确命中，违例数 0
5. `new_card` 的 `kind` 必须在该科目词表内，`card_type` 在九类内，question/answer 均非空
6. JSON 每行可解析
