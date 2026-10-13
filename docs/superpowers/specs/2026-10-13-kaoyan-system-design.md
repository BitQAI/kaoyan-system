# Spec：kaoyan-system 考研陪跑系统

- 日期：2026-10-13
- 状态：待用户审阅
- 使用者：仅本人（BitQAI）
- 场景：2027 考研 · 云南农业大学 095400 林业（热带作物学院）· 2026-12-19 初试（距 67 天）
- 科目：101 政治 · 204 英语二 · 315 化学（农）· 812 植物生理学（重点 315/812）
- 域名：kaoyan.bitqai.com（宝塔 + Let's Encrypt）
- 仓库：https://github.com/BitQAI/kaoyan-system.git（**公开**，部署方式 = 用户自行 clone 到宝塔）

---

## 一、问题背景与目标

白天上班，**以听为主**（碎片化、手机、后台播放）；晚间/周末**看 + 测**。英语政治相对较好，精力集中在 315（26 章）与 812（12 部分）。需要一个：
1. 以**知识点为锚点**、按**考纲权重**排序的学习系统；
2. 每科**加权进度**可见（315/812 为重点）；
3. 支持**含公式/结构式/图**的考点展示（315 化学、812 机制图尤甚）；
4. 应用内 **AI 问答**，对话历史**按知识点/题目为单位**归档；
5. 训练库（选择题/背题卡/错题本/收藏）完整闭环。

**原型**（已自验渲染与交互）：`.build/ui_prototype.html`（5 页 + AI 抽屉 + 多媒体演示）。

## 二、已验证的关键事实（2026-10-13 实测）

| 项 | 结论 |
|---|---|
| TTS 通道 | 百炼 DashScope 原生端点 `POST {host}/api/v1/services/aigc/multimodal-generation/generation`，模型 `qwen3-tts-flash`，返回音频 URL（wav），长文本一次可合（~500 字） |
| 文本对话通道 A | **opencode go 网关** `https://opencode.ai/zen/go/v1`（OpenAI 兼容 + SSE），模型 `deepseek-v4.1-flash`（推理模型，返回 `reasoning_content`）；**必须带 `x-opencode-session` 头（会话 ID）**——与"每知识点/题目一个对话线程"天然对应，利于厂商侧缓存 |
| 文本对话通道 B（兜底） | 百炼兼容端点 `{host}/compatible-mode/v1/chat/completions`，同款 `deepseek-v4.1-flash` 已验证可用 |
| 注意 | opencode go 文档注明面向 coding agent、流量受滥用监测、月额度滚动窗口限制 → 个人低频使用，保留百炼兜底；服务器侧部署时实测两通道连通性再定默认 |
| 音色 | 用户选定**男声**（默认 Ethan，qwen3-tts-flash 音色），样本见 `.build/tts_samples/` |
| 媒体生成 | KaTeX+mhchem（公式/反应式，前端渲染）· RDKit（结构式→SVG，构建期）· matplotlib（数据图表）· 示意图三来源：教材裁图 > Wikimedia Commons CC > AI(qwen-image) 人工核验 |

## 三、范围

**做**：101/315/812 全量听学内容（考点→音频/看卡/训练）、204 仅进度看板（无内容）、AI 问答与线程、训练库、加权进度、每日计划、宝塔部署文档、GitHub 推送。

**不做**：多用户/注册、社交分享、204 的音频与题库、教材扫描全文 OCR、真题题库录入（后续可选）、安卓/iOS 原生 App（用 PWA）。

## 四、架构

```
【Mac · 构建期】（仓库 scripts/，可重复运行）
  merged.html ─解析─▶ content.json ─┬─ 口语化 → spoken
                                    ├─ 媒体：mhchem/RDKit/matplotlib/教材裁图/Commons/AI
                                    ├─ TTS(qwen3-tts-flash) → audio/*.mp3   ← ≤60s/知识点，长点拆段
                                    └─ 题库/卡片（Claude 离线生成，人工抽查）
                                          ↓ dist/（版本 hash）
【GitHub】BitQAI/kaoyan-system（公开）
  仅代码 + 文本内容 + 小型媒体资产 + 音频生成脚本；**不含**密钥与教材裁图
【云服务器 · 宝塔】（用户自行部署，按 DEPLOY.md）
  Nginx(HTTPS) ├── 静态：web/ + audio/ + media/（Range 支持，不经后端）
               └── /api → FastAPI 127.0.0.1:8000（uvicorn 1 worker）
  SQLite kaoyan.db（WAL）· .env（密钥，600）· 每日 02:00 备份×7
```

技术栈：Python 3.10+ / FastAPI / SQLite / 原生 JS PWA（无框架）/ Nginx。音频推荐**服务器端一条命令生成**（避免上传大文件）；也可本地生成后 rsync。

## 五、数据模型

### 5.1 content.json（构建期产出）

```json
{"version":"hash","generated_at":"…",
 "subjects":[{"id":"812","name":"植物生理学","score":150,"has_content":true,
  "chapters":[{"id":"812-04","name":"第四章 植物的光合作用","tier":1,
    "weight_center":23,"weight_range":[16,28],"syllabus":"…大纲原文…",
    "points":[{"id":"812-04-01","text":"考点句原文","spoken":"口语化朗读文本",
      "tags":["基础"],"listen_ok":true,
      "media":[{"type":"formula|structure|chart|diagram","src":"media/812-04-01-1.svg",
                "tex":"Ψ_w=Ψ_s+Ψ_p+Ψ_m","caption":"…","source":"rdkit|matplotlib|commons|ai|textbook",
                "license":"CC BY-SA 4.0","attribution":"…"}],
      "audio":[{"src":"audio/812-04-01.mp3","dur":42}]}],
    "quiz":[{"id":"q8120401","stem":"…","media":[],"options":["…"],"answer":2,
             "explain":"…","point_id":"812-04-01"}],
    "cards":[{"id":"c8120401","front":"名词解释：光呼吸","back":"…","point_id":"…","media":[]}]}]}],
 "subjects_note":"204 无内容，仅进度看板"}
```

### 5.2 SQLite（运行期）

| 表 | 字段 | 说明 |
|---|---|---|
| `progress` | point_id PK, state, updated_at | state ∈ new/listened/half/known/review |
| `audio_pos` | clip_id PK, position_sec, plays, last_at | 断点续听 |
| `quiz_attempts` | id, quiz_id, chosen, correct, ts | |
| `wrong_book` | quiz_id PK, wrong_count, last_wrong_at, streak, resolved_at | 连对 2 次自动出本 |
| `favorites` | type(point/quiz/card/clip), ref_id, created_at | |
| `ai_threads` | id, owner_type(point/quiz/free), owner_ref, title, updated_at | 一锚点一线程；线程 id ↔ `x-opencode-session` |
| `ai_messages` | id, thread_id, role, content, reasoning, ts | reasoning 单独存，默认折叠 |
| `daily_log` | date PK, listen_sec, clips, cards, quiz_n | 打卡与统计 |
| `settings` | k, v | 每日目标/音色/倍速等 |

**进度算术**：状态系数 known=1 / half=0.5 / listened=0.3 / review=0.6（复习中）→ 章节完成度 → 科目加权进度 = Σ(章完成度×权重中心)/Σ权重；同时展示原始完成度。

## 六、AI 设计

- 默认通道 opencode go（`deepseek-v4.1-flash`，SSE 流式）；`.env` 开关 `AI_PROVIDER=opencode|bailian`，部署时连通性实测后定默认。
- 线程=锚点：知识点/题目自动建线程；请求头 `x-opencode-session` = 线程 ID（稳定会话，利于缓存，也是"按知识点归档对话"的实现基础）。
- 上下文注入：助教人设 + 当前知识点原文/题干+答案+解析 + 最近 10 轮。
- 快捷指令：讲简单点 / 举个例子 / 按考试答题格式给标准答案 / 出 2 道相关的题 / 我错在哪。
- `reasoning_content` 折叠存显；回答固定前缀"AI 生成，请对照教材"。
- 密钥仅存服务器 `.env`；前端零暴露；单用户并发限 1。

## 七、多媒体方案（四层）

| 层 | 生成方式 | 存放 |
|---|---|---|
| 公式/反应式 | 构建期识别 → `tex` 字段（LaTeX/mhchem），前端 KaTeX+mhchem 渲染（内联打包） | JSON 内 |
| 化学结构式 | SMILES → RDKit 构建期 SVG | `media/*.svg` |
| 数据图表 | 滴定曲线/光响应曲线等 → matplotlib PNG | `media/*.png` |
| 示意图 | 优先级：①教材裁图（本地生成，**不入库**，部署时单独上传）②Wikimedia Commons（API 检索 + CC 过滤 + 自动署名）③AI 生成（qwen-image，人工核验后入库，标注"AI 生成"） | `media/*` |

联动：含媒体知识点标 `含图` → 听单自动改排晚间"看"；音频语境公式按 `spoken` 中文读法朗读；图下必带来源/许可/图注。

## 八、页面（5 Tab + AI 抽屉）

见原型 `.build/ui_prototype.html`（已验证：切 Tab/播放/勾状态/答题/翻卡/问 AI 全部可交互，控制台零报错）。
1. **今日**：倒计时、今日听单（碎片凑时长）、晚间任务（看/测）、四科加权进度环、连续打卡、"今天补 X 个知识点音频可追平"
2. **听**：队列播放器（±15s、倍速、单段循环、断点续听、锁屏后台）+ 按计划/章节/收藏三种队列；知识点级 ≤60s 音频连续播报；`含图` 标
3. **看**：科目→章节（权重徽章+进度）→考点卡（三态轮转、收藏、AI、媒体区）
4. **测**：选择题 / 背题卡 / 错题本 / 收藏重练；答题即判+解析+追问 AI
5. **我的**：加权/原始进度、AI 对话历史（按锚点分组）、音色/倍速/每日目标/备份/改密

## 九、内容管线（scripts/，可重复运行）

1. **解析**：merged.html（四科全景，默认输入路径 `../master_eaxm/2027考研_四科知识全景与章节权重.html`，可配置）→ 315 26 章、812 12 部分、101 6 模块考点级条目 + 权重报告数据 → content 骨架。
2. **口语化**：符号词典（Δ→德尔塔、Ψ_w→水势、H⁺-ATP 酶、化学式→中文名、→读"生成"…）→ `spoken`。315 为重点；词典可增量维护。
3. **切段（TTS ≤60s）**：每条知识点 `spoken` 按 ≤220 汉字切 1-N 段（`point_id`、`-p1/-p2`）；机制标注并入该点音频。
4. **TTS**：qwen3-tts-flash 男声（Ethan）批量合成 wav → ffmpeg → mp3（64kbps mono）；失败重试与断点续跑；抽听验收。
5. **媒体**：按七节四层生成/检索/核验；教材裁图工具（本地，PDF 页码+区域配置）。
6. **题库/卡片**：Claude 离线生成（量：每章 8-15 选择 + 名解/简答卡），人工抽查 ≥95% 正确率后入库；含图题带 media。
7. **打包**：`dist/` = content.json + media/ + （可选）audio/ + 版本 hash；`make audio` 支持服务器端生成。

## 十、每日计划

听单 = 按「章权重 × 未完成度」排序取知识点音频，凑设定分钟数（含图挪晚间）；看单 = 到期复习（半/不会 + 错题关联）+ 新卡；测单 = 当日章节题 + 错题重练；每 7 天第一梯队冲刺测。参数可调（每日听 40 分钟 / 看 8 点 / 测 15 题为默认）。

## 十一、部署（DEPLOY.md 随仓库交付）

1. 宝塔：子域 `kaoyan.bitqai.com` A 记录 → 新建站点 → Let's Encrypt。
2. `git clone` → `pip install -r requirements.txt`（建议宝塔 Python 项目管理器，uvicorn 127.0.0.1:8000，1 worker）。
3. 配置 `.env`（OPENCODE_GO_KEY / BAILIAN_KEY / APP_PASSWORD_HASH / SESSION_SECRET，600 权限）→ `python scripts/gen_audio.py`（服务器端生成音频，需 BAILIAN_KEY）→ `python scripts/init_db.py`。
4. Nginx：`/api` 反代；静态目录含 web/audio/media；开启 Range。
5. 备份：宝塔计划任务每日 02:00 备份 `data/kaoyan.db`×7。
6. 验收清单（见十二）。

**仓库安全约束（公开仓库）**：不提交任何密钥（仅 `.env.example`）；教材裁图不入库；`.gitignore` 覆盖 `.env`/`data/`/`dist/`/`*.pdf`/`private-media/`。

## 十二、验收标准

- 手机 Safari/Chrome：一次登录 90 天免登；锁屏/后台连续播放、±15s/倍速/断点续听正确；电脑同进度。
- 训练库闭环：错题入本、连对 2 次出本、收藏重练可用；AI 对话按锚点分组可回看续聊。
- 内容抽查：TTS 抽听 10 段可懂无乱码；题库抽 50 题正确率 ≥95%；媒体显示与署名完整。
- 部署：按 DEPLOY.md 从零部署 ≤30 分钟；备份可恢复演练通过。
- 性能：首页 4G <1.5s；单段音频 ≤1 分钟、mp3 ≤0.6MB。

## 十三、里程碑

M1（约 1 天）后端骨架+登录+进度 API+五页接真数据（先 812 单科）→ M2（约 1 天）812 全科管线（音频/题库/媒体）→ M3（约 0.5-1 天）315+101 内容 → 推送 GitHub + DEPLOY.md → M4 AI 通道接入与打磨（错题本/收藏/每日计划）。

## 十四、风险

| 风险 | 对策 |
|---|---|
| opencode go 通道 ToS/额度/连通性 | 双通道可切、部署实测、低频使用 |
| TTS 口语化差错（化学符号） | 词典+人工抽听；错读点单独修正重生成 |
| 教材裁图版权（公开仓库） | 不入库，个人服务器使用，部署文档单独步骤 |
| 题库质量 | 人工抽查门槛（≥95%）+ 应用内"报错"入口（记录待修） |
| 67 天时间压力 | 里程碑压缩（≤3 天开发）；内容按 812→315→101 优先级增量上线 |
