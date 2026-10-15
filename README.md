# kaoyan-system · 考研陪跑

个人考研学习系统：**白天碎片化听，晚间看 + 测**。以知识点为锚点、按考纲权重排序，
覆盖 101 政治 / 315 化学（农）/ 812 植物生理学 三科全量内容（204 英语仅进度看板）。

- 前端：原生 JS PWA（5 个 Tab：今日 / 听 / 看 / 测 / 我的 + AI 抽屉），手机优先；液态玻璃视觉（跟随系统浅/深色）
- 后端：FastAPI + SQLite（单用户密码登录）
- AI 问答：opencode go 网关（deepseek-v4.1-flash，SSE 流式），对话按知识点/题目成线程；百炼可切换
- 音频：按知识点切段（≤60s），百炼 qwen-audio-3.1-tts-next（男声）批量生成，Nginx 静态直出
- 媒体：KaTeX 公式 · RDKit 结构式 · matplotlib 图表 · 教材裁图（个人使用，不入库）
- 记忆机制：5,349 条原子单元独立间隔调度（三档评分 忘了/吃力/秒答；距初试 21 天进入压缩期）；
  复习模式为遮罩检索（先回忆 → 揭示原文 → 评分），队列最不熟优先、跨科交错

## 快速开始（本地）

```bash
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
cp .env.example .env   # 填 KY_PASSWORD_HASH / KY_SESSION_SECRET / AI keys
.venv/bin/uvicorn app.main:app --port 8010
# 浏览器打开 http://127.0.0.1:8010
```

## 目录结构

```
app/            后端（routers: auth/content/progress/review/media_state/quiz/plan/settings/ai）
web/            前端 PWA（js/ 各页面模块；vendor/katex 内联公式渲染）
content/        content.json（考点/题库/媒体引用）+ audio/（音频，不入库）+ quiz/（题库源 JSON）
scripts/        内容管线：parse_content → normalize → gen_notes/gen_cues（解析与线索标题）→ gen_audio → gen_media → crop_textbook → validate_content → package
tests/          pytest（110+，含真实内容端到端）
docs/           superpowers spec/plan + 音色样本
DEPLOY.md       宝塔部署指南（域名 kaoyan.bitqai.com）
```

## 内容管线速查

```bash
.venv/bin/python scripts/parse_content.py        # HTML → content.json 骨架
.venv/bin/python scripts/gen_audio.py --engine qwen_audio   # TTS 批量（断点续跑）
.venv/bin/python scripts/gen_media.py structures # RDKit 结构式（另见 charts/commons）
.venv/bin/python scripts/crop_textbook.py --config content/figures_textbook.json [--attach]
.venv/bin/python scripts/validate_content.py [--merge]      # 校验/合并题库
```

## 部署

见 [DEPLOY.md](DEPLOY.md)（宝塔 + Let's Encrypt + Nginx 反代 + 每日备份）。

## 说明

- 内容为个人复习整理与生成，不保证与官方大纲逐字一致；权重为推算区间，非官方
- 教材扫描裁图仅个人学习使用，不随仓库分发
