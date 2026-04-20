# Signal FM

> AI-Powered Domain Radio · 垂直领域实时 AI 电台

Signal FM 是一个面向垂直领域知识工作者的实时 AI 广播系统。它持续监控目标领域的全网信息流，由 LLM 筛选出真正有价值的内容，实时生成播报稿并合成为音频，以 FM 电台的方式持续播出——无需手动触发，永远在线，永远只播最值得听的那条。

**"不是把内容做成播客，而是把电台这个形态，用 AI 重新发明一遍。"**

---

## 核心特性

| 特性 | 说明 |
|------|------|
| **持续自动** | 永续运行，无需手动触发，就像真正的电台——没有人在打开它之前它就已经在播了 |
| **智能评分** | GLM-4-Flash 四维评分（新颖性/重要性/领域匹配/时效性），只有 ≥70 分的内容才能上播，过滤掉 80% 噪声 |
| **实时抓取** | 自主爬取 RSS、NewsAPI、网页，内容自动流入，无需用户参与 |
| **幻觉防控** | 生成脚本时强制注入信源标记，禁止 LLM 补全未在原文出现的数据 |
| **企业级** | 支持私有化部署，B2B 订制频道，适合金融/制造/投研敏感行业 |

---

## 系统架构

```
[ LAYER 1 · DATA INGESTION ]
  RSS Feeds ──┐
  NewsAPI    ─┼──► Dispatcher ──► Redis Stream ──► URL Dedup Hash
  Playwright ─┘  (APScheduler)   (Message Queue)   (SHA256)

[ LAYER 2 · AI INTELLIGENCE ]
  Redis Stream ──► Score Worker (GLM-4-Flash, ~100ms/item)
                   ├─[score ≥ 70]──► Script Generator (GLM-4)
                   └─[score < 70]──► DISCARD

[ LAYER 3 · AUDIO SYNTHESIS ]
  Script ──► TTS Router
              ├── CosyVoice (本地, 低延迟)
              └── Edge TTS  (云端备份)
              ──► Audio Cache (MinIO)

[ LAYER 4 · BROADCAST ENGINE ]
  Audio Queue ──► Priority Scheduler ──► FFmpeg Mixer
                                          ├── HLS Stream ──► Web Player
                                          ├── RTMP ────────► Smart Speaker
                                          └── RSS ─────────► Podcast App

[ LAYER 5 · INTERFACE ]
  WebSocket ──► Real-time Metadata
  REST API  ──► 频道配置 / 播放控制 / 数据看板
  Bot Push  ──► Feishu / WeCom
```

---

## 技术栈

| 组件 | 方案 |
|------|------|
| 抓取调度 | APScheduler + Celery |
| 消息队列 | Redis Stream |
| LLM 评分 | GLM-4-Flash |
| 脚本生成 | GLM-4 |
| TTS | CosyVoice 2.0 / Edge TTS |
| 推流 | FFmpeg → Icecast (HLS) |
| 音频缓存 | MinIO |
| 前端 | React + WebSocket |
| 后端 | FastAPI + Python |

---

## 快速开始

```bash
# 克隆项目
git clone https://github.com/fxp007/signal-fm.git
cd signal-fm

# 配置环境变量
cp .env.example .env
# 编辑 .env，填入 GLM API Key 等配置

# 启动服务
docker-compose up -d

# 访问 Web 播放器
open http://localhost:3000
```

---

## 项目结构

```
signal-fm/
├── backend/
│   ├── ingestion/       # 数据抓取层（RSS/NewsAPI/Playwright）
│   ├── intelligence/    # AI 评分与脚本生成
│   ├── synthesis/       # TTS 音频合成
│   ├── broadcast/       # 音频队列与调度
│   └── api/             # REST API & WebSocket
├── frontend/            # Web 播放器（React）
├── bots/                # 飞书/企微 Bot
├── docker-compose.yml
└── .env.example
```

---

## 发布路线图

- **Phase 1 · MVP（2026 Q2）**：RSS 接入、GLM 评分、Edge TTS、基础播放器、飞书 Bot
- **Phase 2 · Public Beta（2026 Q3）**：CosyVoice、频道编辑器、突发插播、Pro 订阅
- **Phase 3 · GA（2026 Q4）**：私有化部署、企业知识库接入、音色克隆
- **Phase 4 · V2（2027 Q1）**：数据飞轮、多语言、双主播对话、频道市场

---

## 商业模式

| | Free | Pro | Enterprise |
|--|------|-----|-----------|
| 价格 | ¥0/月 | ¥49/月 | 定制/年 |
| 频道数 | 1 | 5 | 无限 |
| 播出时长 | 每日 30 分钟 | 无限 | 无限 |
| 私有化部署 | ❌ | ❌ | ✅ |

---

*Signal FM PRD v1.0 · April 2026*
