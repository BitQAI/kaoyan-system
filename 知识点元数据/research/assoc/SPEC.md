# 关联数据生成规范（前置 / 相关 / 易混）

目标：给 315 / 101 / 204 的每个知识点补上 `prerequisites`、`related`、`confusables`。
812 已有这套数据，是对齐基线。

## 基线（812 实测，130 点）

| 字段 | 含义 | 每点平均 | 有点位占比 |
|---|---|---|---|
| `prerequisites` | 学这个点之前必须先会的点 | 0.96 | 118/130 |
| `related` | 同一主题下应当对照看的点 | 1.25 | 128/130 |
| `confusables` | 容易混淆的点，附「最关键区别」 | 0.64 | 83/130 |

`related` 绝大多数是同章（158 同章 / 5 跨章）。**不要为凑数硬连**，没有就留空。

## 输入

`research/assoc/batches/<sid>-aN.json`：本批点位，含 `id / chapter / chapter_name / title / point / keywords / cards[设问]`。
`research/assoc/<sid>-index.json`：全科索引（`id / chapter / chapter_name / title / brief`），跨章引用时查 id。

## 输出

`research/assoc/out/<sid>-aN.jsonl`，**每点一行**，字段固定：

```json
{"id":"3150101","prerequisites":["3150102"],"related":["3150103","3150104"],
 "confusables":[{"name":"真溶液 vs 胶体","point_id":"3150103",
                 "distinction":"以分散质粒径 1 nm 为界；胶体有丁达尔效应"}]}
```

## 硬约束

| 项 | 规则 |
|---|---|
| 数量 | `prerequisites` ≤3、`related` ≤3、`confusables` ≤2；**允许全空** |
| id | 必须是本科目 `index` 里存在的 id，不得自引用，同一字段内不重复 |
| `prerequisites` | 只写**学习顺序在前的点**（章号小于或等于本点） |
| `confusables[].name` | ≤20 字，形如「A vs B」 |
| `confusables[].distinction` | ≤60 字，写**可判定的分界**（数值、条件、方向、适用对象），不写「概念相近」这类空话 |
| `confusables[].point_id` | 明确的对应点；若这个易混体不是某个独立点（如跨学科名词），填 `null` |
| 语义 | 只连**真的需要一起看**的点。答不出「为什么这两个要连」就别连 |

## 判定要点

- **prerequisites**：去掉它，本点会看不懂。例：讲「缓冲溶液 pH 计算」前置是「弱酸解离平衡」。
- **related**：同章同主题的平行点。例：「溶胶稳定性」相关「电解质聚沉」。
- **confusables**：做题时会被当成同一个东西的两个点。特征是**有明确的分界指标**。
  政治科尤其多：如「基本经济制度 vs 根本政治制度」，分界是「所有制 / 政权组织形式」。
- 204 是英语技巧类，`prerequisites` 多为空，`related` 多为同题型内的相邻技巧。

## 自检

```
python3 scripts/apply_assoc.py <sid>
```
必须 `问题数 0`。它会检查：行数、id 存在性、自引用、数量上限、字数上限。
