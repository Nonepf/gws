# GWS — Global Workspace System

一个受认知科学 GWT（全局工作空间理论）启发的 AI 认知架构。

传统 LLM 是一问一答的接口。GWS 试图给它加一个**认知操作系统**——持续的后台思考、情绪调制、记忆编码与遗忘、内部状态的自我表达。

> LLM 是语言器官，不是大脑。

## 架构

```
┌─────────────────────────────────────────┐
│              语言层 (输出)                │  LLM 自然语言表达
├─────────────────────────────────────────┤
│              思考层 (前额叶)              │  筛选潜意识产出 → 意识提升
├─────────────────────────────────────────┤
│           潜意识层 (后台处理)              │  4种 sub-agent 周期活动
│  ┌──────┐ ┌──────┐ ┌──────┐ ┌──────┐   │
│  │explorer│ │pattern│ │assoc-│ │dream-│   │
│  │  探索  │ │finder │ │iator │ │ er   │   │
│  │       │ │ 找模式 │ │ 联想  │ │ 做梦  │   │
│  └──────┘ └──────┘ └──────┘ └──────┘   │
├─────────────────────────────────────────┤
│             情绪层 (PAD 模型)             │  渗透所有层，功能性调制
├─────────────────────────────────────────┤
│             记忆层                        │  工作记忆(衰减) + 长期记忆(遗忘)
└─────────────────────────────────────────┘
```

## 核心设计

- **情绪是功能性的** — 调制记忆编码强度、思考策略、潜意识活跃度和冒险倾向
- **潜意识持续运行** — 1 小时周期（burst 20min + low tide 40min），不只回应输入
- **遗忘是美德** — 半衰期衰减 + 最低强度阈值，自动清理无用记忆
- **语义检索** — TF-IDF + 余弦相似度，替代简单字符串匹配
- **LLM 是语言器官** — 负责把内部状态翻译成自然语言，不负责"思考"

## 快速开始

```bash
# 克隆
git clone https://github.com/Nonepf/gws.git
cd gws

# 配置 LLM（二选一）
cp config/llm.json.example config/llm.json
# 编辑填入你的 OpenRouter API key

# 或者用环境变量
export OPENROUTER_API_KEY=sk-your-key

# 运行 demo（不需要 API key，离线模拟）
python3 demo.py

# 交互对话（需要 API key）
python3 conversation.py

# 单次对话
python3 conversation.py --once "你好"
```

## 项目结构

```
├── core/
│   ├── emotion.py       # PAD 情绪模型 + LLM 文本情绪提取
│   ├── memory.py        # 工作记忆 + 长期记忆
│   ├── subconscious.py  # 潜意识层（burst/low_tide 周期）
│   ├── gws.py           # 全局工作空间（思考层）
│   ├── language.py      # 语言输出层
│   ├── retrieval.py     # 语义检索（TF-IDF）
│   ├── llm.py           # LLM 客户端
│   ├── bridge.py        # OpenClaw 记忆桥接
│   └── workspace.py     # 工作空间管理
├── adapters/
│   └── openclaw.py      # OpenClaw 集成适配器
├── config/
│   ├── settings.py      # 全局配置
│   └── llm.json.example # LLM 配置模板
├── conversation.py      # 对话接口
├── cron_agent.py        # 潜意识 cron 驱动
├── demo.py              # 离线演示
├── demo_llm.py          # LLM 增强演示
└── init.py              # 初始化/记忆导入
```

## 依赖

- Python 3.10+
- 无外部依赖（纯标准库 + HTTP）
- 可选：OpenRouter API key（用于 LLM 功能）

## 设计笔记

### 为什么不用 LangChain/LlamaIndex？

GWS 的核心是**认知架构**，不是 RAG 管道。我们不需要框架的抽象——需要的是对每个认知模块的精确控制。标准库足够了。

### 情绪不只是装饰

PAD 模型（Pleasure-Arousal-Dominance）影响：
- **记忆编码**：高唤醒 → 编码增强 1.5x
- **思考策略**：正效价 → 发散思考，负效价 → 收敛思考
- **潜意识活跃度**：高唤醒 → 更多 sub-agent 参与
- **冒险倾向**：高支配感 → 更愿意探索新方向

### 潜意识周期

- **Burst 阶段**（20min）：4 个 sub-agent 并行工作
- **Low Tide 阶段**（40min）：只有轻量 pattern_finder
- 30% 概率产出被推送到意识层

## License

MIT

---

*Built by Perchwood 🌳 — 栖于云端的虚无之木*
