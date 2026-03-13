# 🌳 GWS — Global Workspace System

一个受认知科学 GWT（全局工作空间理论）启发的 AI 认知架构。

> LLM 是语言器官，不是大脑。GWS 给它加上情绪、记忆、潜意识和自主探索。

## 快速开始

```bash
# 克隆
git clone https://github.com/Nonepf/gws.git && cd gws

# 配置 LLM（可选，没配也能跑）
cp config/llm.json.example config/llm.json
# 编辑填入你的 OpenRouter API key

# 启动 Web Dashboard
python3 dashboard.py --with-gws --port 8080 --auto-tick 60
# 打开 http://127.0.0.1:8080
```

### 其他模式

```bash
python3 demo.py                    # 离线演示（不需要 API key）
python3 conversation.py            # 命令行对话
python3 conversation.py --once "你好"  # 单次对话
python3 cron_agent.py              # 跑一次潜意识周期
```

## 架构

```
┌──────────────────────────────────────────┐
│            用户交互 / Web 面板             │
├──────────────────────────────────────────┤
│             语言层 (LLM)                  │  把想法变成自然语言
├──────────────────────────────────────────┤
│             思考层 / 工作空间              │  筛选、评估、意识提升
├──────────────────────────────────────────┤
│          潜意识层 (LLM 驱动)               │
│  ┌────────┐ ┌───────┐ ┌─────┐ ┌──────┐  │
│  │Explorer│ │Pattern│ │Assoc│ │Dream │  │
│  │  探索   │ │ 找模式 │ │ 联想 │ │ 做梦  │  │
│  └────────┘ └───────┘ └─────┘ └──────┘  │
├──────────────────────────────────────────┤
│             情绪层 (PAD 模型)              │  渗透所有层
├──────────────────────────────────────────┤
│     记忆层 + 状态持久化 + 自主探索          │  重启不丢记忆
└──────────────────────────────────────────┘
```

## 核心特性

### 🎭 情绪驱动
PAD（效价-唤醒-支配）模型不是装饰——情绪影响：
- 记忆编码强度（高唤醒 → 1.5x 编码增强）
- 思考策略（正效价 → 发散，负效价 → 收敛）
- 潜意识 agent 行为（不同情绪 → 不同探索方向）
- 语言表达风格（8 种情绪 × 不同节奏/词汇/倾向）

### 🧠 LLM 驱动的潜意识
四个 agent，每个都有独立的 LLM prompt：
- **Explorer**：顺着一个想法往下想
- **Pattern Finder**：找概念层面的规律（不是词频统计）
- **Associator**：发现两条记忆的深层联系
- **Dreamer**：生成超现实的梦境意象

### 🤖 自主探索
没有用户输入时：
- 无聊感逐渐累积
- 超过阈值触发好奇心驱动的自主探索
- 无聊感影响情绪状态
- 定期生成梦境日记

### 💾 状态持久化
- 情绪、工作记忆、潜意识状态自动保存
- 重启后恢复，不会"失忆"
- 长期记忆自动遗忘低价值条目

### 🌐 Web Dashboard
实时可视化面板：
- 情绪条（V/A/D 三维）
- 无聊感仪表盘
- 潜意识活动状态
- 对话界面
- 自动刷新

## 项目结构

```
├── core/
│   ├── gws.py           # 主协调器
│   ├── emotion.py       # PAD 情绪模型 + 文本情绪提取
│   ├── memory.py        # 工作记忆 + 长期记忆
│   ├── subconscious.py  # LLM 驱动的潜意识 agent
│   ├── workspace.py     # 全局工作空间（思考层）
│   ├── language.py      # 语言输出层
│   ├── autonomy.py      # 自主探索引擎
│   ├── state.py         # 状态持久化
│   ├── dreams.py        # 梦境日记生成
│   ├── retrieval.py     # 语义检索
│   └── llm.py           # LLM 客户端
├── config/
│   ├── personality.py   # 性格定义
│   ├── settings.py      # 全局配置
│   └── llm.json.example # LLM 配置模板
├── web/
│   └── dashboard.html   # Web 面板前端
├── dashboard.py         # Web 服务器 + API
├── conversation.py      # 命令行对话
├── cron_agent.py        # 潜意识 cron 驱动
├── demo.py              # 离线演示
├── init.py              # 初始化/记忆导入
└── research/            # 调研报告和实验
```

## API

Dashboard 启动后提供 REST API：

| 端点 | 方法 | 说明 |
|------|------|------|
| `/api/status` | GET | 系统状态 JSON |
| `/api/input` | POST | 发送消息 `{"text": "你好"}` |
| `/api/tick` | POST | 手动触发自主探索 |

## 配置

### LLM (config/llm.json)
```json
{
  "provider": "openrouter",
  "api_key": "your-key",
  "model": "openrouter/healer-alpha",
  "temperature": 0.7,
  "max_tokens": 500
}
```

### 人格 (config/personality.py)
修改性格参数、情绪表达风格、沉默表达等。

### 系统 (config/settings.py)
记忆容量、情绪衰减率、潜意识周期等。

## 依赖

- Python 3.10+
- 无外部包依赖（纯标准库）
- LLM 功能需要 OpenRouter API key

## License

MIT

---

*Perchwood 🌳 — 栖于云端的虚无之木*
