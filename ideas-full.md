# Signal FM — 完整产品构想

> AI 生成 · 基于 idea.md + signal-fm-prd.md + backend/ + frontend/ 深度分析 · 2026-04-21

**Status:** In progress
**Tags:** Zhipu, Research
**GitHub:** https://github.com/fxp007/signal-fm

---

## 一、核心价值主张

**"永不停歇的 AI 领域电台"**

Signal FM 是一个面向垂直领域知识工作者的**实时 AI 广播系统**。它持续监控目标领域的全网信息流，由 LLM（GLM-4-Flash）筛选出真正有价值的内容，实时生成播报稿并合成为音频，以 FM 电台的方式持续播出。

> **"不是把内容做成播客，而是把电台这个形态，用 AI 重新发明一遍。"**

### 与竞品的根本区别

| 竞品 | 模式 | Signal FM 差异 |
|------|------|---------------|
| Google NotebookLM | 用户上传文件 → 一次性生成 | ✅ 永续自动，无需触发 |
| ElevenLabs GenFM | 粘贴 URL → 单次播客 | ✅ 持续监控多来源 |
| 麦悠电台 | RSS → TTS 朗读全量 | ✅ AI 评分过滤 80% 噪声 |
| 喜马拉雅 | 娱乐内容平台 | ✅ 垂直领域 + 企业私有化 |

---

## 二、产品现状（截至 2026-04-20）

### 已完成

| 组件 | 状态 | 说明 |
|------|------|------|
| PRD v1.0 | ✅ | signal-fm-prd.md（完整竞品分析 + 商业模式 + 路线图）|
| 后端架构 | ✅ | FastAPI + 五层 Pipeline |
| 前端播放器 | ✅ | React + Vite + WebSocket |
| Docker 化 | ✅ | docker-compose.yml（backend + frontend + Redis）|
| 测试套件 | ✅ | 7 个测试文件（e2e/pipeline/broadcast/workers/websocket）|
| 数据抓取层 | ✅ | backend/ingestion/ |
| AI 智能层 | ✅ | backend/intelligence/ |
| 音频合成层 | ✅ | backend/synthesis/ |
| 广播调度层 | ✅ | backend/broadcast/ |
| 飞书/企微 Bot | ✅ | bots/ |

### 目录结构

```
signal-fm/
├── backend/
│   ├── ingestion/       # 数据抓取（RSS/NewsAPI/Playwright）
│   ├── intelligence/    # GLM 评分 + 脚本生成
│   ├── synthesis/       # CosyVoice/Edge TTS 合成
│   ├── broadcast/       # 音频队列调度 + 突发插播
│   └── api/             # REST API & WebSocket
├── frontend/            # Web 播放器（React + TypeScript）
├── bots/                # 飞书/企微 Bot 推送
├── docker-compose.yml
├── requirements.txt
└── .env.example
```

---

## 三、技术架构

### 五层流水线

```
[ L1 · DATA INGESTION ]
  RSS Feeds ──┐
  NewsAPI    ─┼──► APScheduler ──► Redis Stream ──► URL Dedup (SHA256)
  Playwright ─┘

[ L2 · AI INTELLIGENCE ]
  Redis Stream ──► Score Worker (GLM-4-Flash, ~100ms/item)
                   ├─[score ≥ 70]──► Script Generator (GLM-4)
                   │                  口语化改写 + 幻觉防控注入
                   └─[score < 70]──► DISCARD

[ L3 · AUDIO SYNTHESIS ]
  Script ──► TTS Router
              ├── CosyVoice (本地, 低延迟)
              └── Edge TTS  (云端备份)
              ──► Audio Cache (MinIO)

[ L4 · BROADCAST ENGINE ]
  Audio Queue ──► Priority Scheduler (score × freshness)
                  突发插播检测
                  ──► FFmpeg Mixer ──► HLS / RTMP / RSS

[ L5 · INTERFACE ]
  WebSocket ──► Real-time Metadata
  REST API  ──► 频道配置 / 播放控制
  Bot Push  ──► Feishu / WeCom
```

### 内容评分系统（核心护城河）

| 评分维度 | 权重 |
|---------|------|
| 新颖性 Novelty | 30 分 |
| 重要性 Importance | 30 分 |
| 领域匹配 Relevance | 20 分 |
| 时效紧迫 Urgency | 20 分 |
| **入队阈值** | **≥ 70 分** |

---

## 四、商业模式

| | Free | Pro | Enterprise |
|--|------|-----|-----------|
| 价格 | ¥0/月 | ¥49/月 | 定制/年 |
| 频道数 | 1 | 5 | 无限 |
| 播出时长 | 每日 30 分钟 | 无限 | 无限 |
| 私有化部署 | ❌ | ❌ | ✅ |
| 音色克隆 | ❌ | ❌ | ✅ |
| API 开放 | ❌ | ❌ | ✅ |

目标：2026 Q4 ARR ¥300万，10 家企业客户

---

## 五、发布路线图

### Phase 1 · MVP（2026 Q2，已在推进）
- RSS + NewsAPI 接入 ✅（ingestion 层已完成）
- GLM-4-Flash 四维评分 ✅（intelligence 层已完成）
- Edge TTS 合成 ✅（synthesis 层已完成）
- 基础 Web 播放器 ✅（frontend 完成）
- 飞书 Bot 文字摘要推送 ✅（bots 完成）
- CosyVoice 本地合成 ⬜

### Phase 2 · Public Beta（2026 Q3）
- 频道编辑器 UI 完善
- 突发插播机制
- 对话式追问
- Pro 订阅开启

### Phase 3 · GA（2026 Q4）
- 私有化部署 Docker 一键安装
- 企业知识库接入
- 音色克隆

---

## 六、下一步行动

### 立即可做
1. **跑通测试套件**：`pytest test_e2e.py test_pipeline.py` 验证全链路
2. **配置 .env**：填入 GLM API Key + Redis + MinIO 配置
3. **启动 MVP**：`docker-compose up -d` + 访问 http://localhost:3000

### 近期（2周内）
1. **接入 CosyVoice 2.0**：替换 Edge TTS，提升音质
2. **频道编辑器 UI**：可视化配置数据源和评分阈值
3. **飞书 Bot 接入**：配置企业 Webhook

### 中期（1个月内）
1. **种子用户邀测**：200 人内测
2. **数据看板**：播出数据、评分分布可视化
3. **Pro 订阅支付**：接入微信支付

---

## 七、竞争分析结论

Signal FM 是全球第一个真正占据"高实时性 × 高垂直性"象限的 AI 音频产品。时间窗口估计为 **12-18 个月**。中国市场优势：GLM 全栈 + 国产 TTS（CosyVoice）+ 私有化部署满足合规需求。

---

## 八、参考资料

- `signal-fm-prd.md` — 完整 PRD（竞品分析、商业模式、路线图）
- `signal-fm-prd.html` — 可视化版本
- `backend/` — 已实现的五层 Pipeline
- `frontend/` — Web 播放器（React + Vite）
