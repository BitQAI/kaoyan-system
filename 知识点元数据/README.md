# 考研知识点元数据

> 面向后续新建的考研应用（只保留 **听 / 记 / 看** 三个视图）的一套标准化知识点元数据。
> **v3.12（2026-10-28）**：四科全部为 `ky-point/3.0`——538 点 / 5293 units / **3171 张卡** / **538 张图示**（全部为图文结合的信息图）。
> 812 为试点；315 / 101 扩卡、204 原子卡重做；三科 408 点已逐点 Exa 核验并补齐图示。
> 权威真源：`master_eaxm/2027考研_四科知识全景与章节权重.html`（只读）。
> 本目录**自包含**：应用只读本目录即可重建三个视图。

---

## 一、当前规模（v3.0）

| 科目 | schema | 章 | 点 | units | 卡片 | 图示 | 状态 |
|---|---|---|---|---|---|---|---|
| 812 植物生理学 | `ky-point/3.0` | 12 | **130** | **1242** | **869** | **130** | 试点完成 |
| 315 化学（农） | `ky-point/3.0` | 26 | 196 | 1997 | **1191** | **196** | 扩卡 + 图示 |
| 101 思想政治理论 | `ky-point/3.0` | 27 | 161 | 1581 | **810** | **161** | 扩卡 + 图示 |
| 204 英语（二） | `ky-point/3.0` | 9 | 51 | 473 | **301** | **51** | 重做 + 图示 |

**三科 3.0 口径（2026-10-28）**：315/101 保留 2.0 题干并扩卡（每点 4–6 张），204 因原卡片一卡多题，
整点重做为原子卡；`card_type`/`answer_points`/`unit_refs` 全部按点重新生成。
`unit` 覆盖率 315 91.6% / 101 91.4% / 204 99.2%，未覆盖 unit 登记为理解性补充。
证据等级（2026-10-28 条款级对齐后）：812 = 122 verified + 8 inferred；315 = 179 / 17；101 = 149 / 12（161/161 已条款级对齐）；204 = 6 / 45（51/51 已对齐，但英语二官方大纲只有题型结构、无考点级条款）。
三科 408 点已逐点 Exa 核验：verified 335 / partial 73 / wrong 0 / risky 0，partial 已按检索结果修正。
每点配 1 张模板图（概念/流程/清单），共 408 张；812 另有 130 张（64 手绘 + 66 模板）。

**812 v3.0 质量核验**：

- `validate.py`：**0 错误 / 0 警告**。
- `check_locator.py`：**524/524 逐字一致（100%）**，4 个新增点为 syllabus/research 溯源，跳过。
- `audit_v3.py`：重复设问 **0**；unit 覆盖 **1150/1242（92.6%）**，其余 92 条登记为理解性补充。
- 卡片：名解 222 / 简答 611 / 论述 20；card_type 九类全覆盖；每点 4–10 张，中位 7。
- 图示：**130 点均有图**（机制/流程/对比/曲线），其余候选见 `research/812-media-suggestions.md`。
- 证据：122 点 `verified`，8 点 `inferred`。
- 音频：`listen.audio=pending`。v2 旧音频（524 段 / 70MB）已于 2026-10-28 删除，`mappings/audio-manifest.json` 的 clips 已清空；重生成时跑 `gen_audio.py` 写回。

---

## 二、目录结构

```
知识点元数据/
├── README.md
├── 字段字典.md              ← 3.0 全部字段
├── 受控词表.md              ← kind / card_type / evidence / source.kind / media.kind
├── 单元生成规范.md           ← units：4–15 条，30–70 字
├── 卡片生成规范.md           ← cards：kind × card_type、拆段、配图
├── 数据校验规则.md           ← E00–E27 / W03–W20
├── UI展示规范.md             ← 内容分区、间距、七类模块、图示、无障碍
├── schema/
│   ├── ky-point.schema.json      ← 3.0（当前）
│   └── ky-point-2.0.schema.json  ← 2.0 备份
├── subjects/
│   ├── 812/
│   │   ├── 812.md                ← 人审真源（章节表 + 知识点表 + 关联表）
│   │   ├── 812.json              ← 机洗真源（build.py 生成）
│   │   ├── 812-units.jsonl       ← 原子单元侧车
│   │   ├── 812-cards-v3.jsonl    ← 卡片分片合并结果
│   │   ├── 812-cards.jsonl       ← finalize 产物
│   │   └── 812-media.json        ← 图示侧车（130 张 SVG）
│   ├── 315/ 101/ 204/            ← 3.0（2026-10-27 迁移）
├── research/
│   ├── <sid>-syllabus.md    ← 官方考纲结构化（812：12 章 80 条）
│   ├── <sid>-sources.md     ← 来源台账（含 ali-* 对齐来源行）
│   ├── <sid>-coverage.md    ← 覆盖矩阵 + 理解性补充清单
│   ├── <sid>-audit.md       ← audit_v3.py 生成
│   ├── align/*.jsonl        ← 101/204 条款级对齐结果（apply_alignment.py 的输入）
│   ├── unit-eval/           ← 424 条未成卡 unit 的评估结论与报告
│   ├── visual/              ← 图示设计规范与状态
│   └── 812/ch00.md … ch11.md ← 逐章调研笔记
├── mappings/
│   ├── legacy-point-map.json
│   └── audio-manifest.json
├── audio/                   ← 已删除（2026-10-28，v2 旧稿与当前 listen 不一致）
├── tests/                  ← 9 个回归测试（pipeline.py 会跑）
├── issues/
│   ├── 全局问题清单.md
│   └── 重复与冲突登记.md
├── scripts/
│   ├── build.py             ← md + units/cards/media 侧车 → json
│   ├── validate.py          ← E/W 校验（3.0 规则全科）
│   ├── audit_v3.py          ← 原子度/覆盖率/重复/卡型分布
│   ├── check_locator.py     ← 仅 html 溯源逐字回溯
│   ├── gen_units_v3.py      ← 4–15 条 unit 生成
│   ├── suggest_media.py     ← 未配图点评分/补图候选
│   ├── gen_media_templates.py ← 概念/流程/清单/对比模板图生成
│   ├── merge_card_shards.py ← 合并子代理卡片分片并校验
│   ├── finalize_cards_v3.py ← 赋 card_id、exam_types、listen
│   ├── extract.py / enrich.py / render_md.py / chem.py / llm.py …
│   └── gen_audio.py / measure_audio.py（本轮未运行）
└── changelog.md
```

---

## 三、层级模型

```
科目 subject（812）
└── 模块 module（植物生理学）
    └── 章节 chapter（tier / weight）
        └── 知识点 point（最小记忆单元）
            ├── units[]       4–15 条原子记忆单元
            ├── cards[]       4–10 张原子卡（kind × card_type）
            ├── listen        代表题朗读稿（audio=pending）
            ├── media[]       图示/公式/插图（12 点）
            ├── prerequisites / related / confusables
            └── exam_evidence 证据等级与来源
```

---

## 四、三个视图消费什么

| 视图 | 消费字段 |
|---|---|
| **听** | `listen.script`（按设问/答案/解析拆块）· `spoken`/`tts`（旧音频）· `media[]` 图示 |
| **记** | `cards[].question` → `answer` → `answer_points` → `analysis`；`card_id` 为主键；`card_type` 决定记忆动作；`media[]` 图示 |
| **看** | `exam_types[]` · `cards[]` · `point` · `title` · `explain` · `exam` · `keywords` · `confusables` · `prerequisites/related` · `media[]` · 章节权重 |

**排序**：`priority`（点级 ★/●/○）是点级排序唯一驱动；章节 `tier` 决定目标曝光次数，二者不混用。

---

## 五、维护流程

### 5.0 一键跑完（推荐）

```bash
# 重建 json + 章节分片 + 箭头内联，再跑校验、审计、locator 回溯、证据复核、测试集
python3 知识点元数据/scripts/pipeline.py

# 只跑校验链（不重建）
python3 知识点元数据/scripts/pipeline.py --check

# 只列步骤
python3 知识点元数据/scripts/pipeline.py --list
```

任何一步失败即中止并返回非零退出码。测试集在 `tests/`，随仓库走；`pipeline.py` 会依次执行。

### 5.1 改内容（人审）

```bash
cd /Users/huajun/Sync/master_eaxm

# 1) 只改 <sid>.md（章节表 / 知识点表 / 关联表）；不要改 point 原句
# 2) 重新构建（同时按章写 subjects/<sid>/chapters/ 分片）
python3 知识点元数据/scripts/build.py
# 3) 校验
python3 知识点元数据/scripts/validate.py
python3 知识点元数据/scripts/check_locator.py
```

`<sid>.json` 仍是唯一入口；`chapters/` 只是同一份数据的按章视图（每片 80–160 KB），
`split_subject.py --check` 可验证分片能无损重组回 `<sid>.json`。改完 json 而不改 md 会被下次
`build.py` 覆盖——所有人工改动都落在 md。

### 5.2 新增/修订 unit

```bash
# 只给新增点或需重写的点生成；已有 unit 默认跳过
python3 知识点元数据/scripts/gen_units_v3.py --ids 8120215 8120216
# 需要重写时加 --force
```

### 5.3 生成卡片（子代理分片）

```bash
# 每个子代理写一个独立分片到 .build/sdd/812-v3/cards/*.jsonl
# 合并并校验（card_type/answer_points/unit_refs/重复题）
python3 知识点元数据/scripts/merge_card_shards.py --shards .build/sdd/812-v3/cards
# 赋 card_id / exam_types / listen
python3 知识点元数据/scripts/finalize_cards_v3.py
python3 知识点元数据/scripts/build.py
python3 知识点元数据/scripts/validate.py
```

### 5.4 配图

- 图示维护在 `subjects/812/812-media.json`，键为 point id，值为 `media[]`；当前 130 张。
- 每条必须含 `kind/caption/alt` 与 `svg` 或 `src`。
- `build.py` 自动合并进 `812.json`；`validate.py` 的 W20 检查完整性。
- 补图候选：`python3 scripts/suggest_media.py`，按「梯队 + 优先级 + 卡型 + 关键词」评分，
  输出 `research/812-media-suggestions.md`；当前 130 点全部有图（64 手绘 + 66 模板化）。
- 模板图批量生成：`python3 scripts/gen_media_templates.py`，只重写 caption 以
  `· 对比图 / · 流程图 / · 清单图 / · 知识结构图` 结尾的条目，不动手绘图。
- 显示规则：听/学/记三视图都渲染 `media`；点击图示打开灯箱放大；375px 不横向溢出，
  窄屏放大后按原生 640px 左右平移。

### 5.5 音频（本轮不做）

v3.0 的 `listen.script` 已更新，但音频仍是旧稿。重生成顺序：

```
用 listen.script 覆盖 spoken
→ gen_audio.py
→ measure_audio.py
→ build.py
→ 把 listen.audio 改为 ready
```

---

## 六、约束与边界

- **源文档只读**：`2027考研_四科知识全景与章节权重.html` 及 4 份上游调研文档不得修改。
- **md 是唯一人工编辑入口**：json 由脚本生成，手改会被覆盖。
- **point 原句保护**：现有 116 点的 `point` 不得改写；改表述只动 `explain/exam/title`。
- **化学式必须 Unicode**：`C₆H₁₂O₆`、`SO₄²⁻`；`SN1/SN2/E1/E2` 保持原样。
- **权重可信度**：`weight_basis` 区分 `官方` / `推算` / `人工估计`；204 章权重合计 116 分已登记 issues。
- **音频待重生成**：812 全量 `listen.audio=pending`；新增点无音频文件，E15 对 pending 点放宽。
- **理解性补充**：113 个未覆盖 unit 已登记在 `research/812-coverage.md`，不计 W17。
- **客观题不在本目录**：v2.0 决策 D16 取消 quiz；812 无选择题卡。

---

## 七、相关文档

- 设计规格：`docs/specs/2026-10-27-812元数据v3.md`
- 实施计划：`docs/plans/2026-10-27-812元数据v3.md`
- UI 规范：`知识点元数据/UI展示规范.md`
- 验收报告：`知识点元数据/research/812-acceptance.md`
- 决策记录（D1–D17）：`docs/specs/2026-10-21-知识点元数据决策书.md`
