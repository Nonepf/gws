# GWS v3 重构日志

## 新增文件
| 文件 | 说明 |
|------|------|
| `core/orchestrator.py` | CognitiveOrchestrator — v3 主协调器 |
| `core/occ.py` | OCC 认知评估引擎（22种情感分类） |
| `core/neurotransmitter.py` | 神经递质模拟（DA/5-HT/皮质醇） |
| `core/safety.py` | 有界自治 + 安全对齐 |

## 重写文件
| 文件 | 主要改动 |
|------|---------|
| `core/emotion.py` | MoodBuffer 心境缓冲器 + CopingStrategy + 神经递质集成 + OCC 接口 |
| `core/drives.py` | HRRL 稳态模型 d(H_t)=Σ|h*-h|^m，替换旧水位线模型 |
| `core/memory.py` | 躯体标记 (somatic_marker) + 情感标注 (affective_tag) + 统一 EmotionState |
| `core/workspace.py` | GWT 点火机制: SalienceCalculator + ignition + broadcast + ConsciousBuffer |
| `core/state.py` | v3 状态持久化 + v2→v3 版本迁移 |

## 增强文件
| 文件 | 改动 |
|------|------|
| `core/blackboard.py` | 相似度去重 + 心境调制衰减 + 过期清理 |
| `core/llm.py` | retry_with_backoff 装饰器（3次重试，指数退避） |
| `core/intentions.py` | 适配 HRRL 维度（energy/information/coherence/social/safety） |
| `core/__init__.py` | 导出所有 v3 模块 |

## 保留不变
- `core/events.py` — 事件总线
- `core/bridge.py` — OpenClaw 桥接
- `core/language.py` — 语言层
- `core/emotion_llm.py` — LLM 情绪提取
- `core/subconscious.py` — 潜意识层（导入已正确）
- `core/urge.py` — 表达欲
- `core/retrieval.py` — 语义检索

## 核心架构变化

### 情感系统
- **v2**: 单一 EmotionEngine + 规则词典 + PAD blending
- **v3**: OCCEngine → PAD + MoodBuffer(短期/长期) + Neurotransmitter调制 + CopingStrategy

### 内驱力
- **v2**: 4个水位线 (curiosity/expression/coherence/social)
- **v3**: HRRL 5维稳态 (energy/information/coherence/social/safety) + 数学驱动函数

### 工作空间
- **v2**: 简单评估 + 提升
- **v3**: SalienceCalculator + 竞争 + 点火(Ignition) + 全局广播

### 记忆
- **v2**: 基础情绪字段
- **v3**: 躯体标记 + 情感标注 + 增强的情绪调制编码

### 安全
- **v2**: 无
- **v3**: BoundedAutonomy + SystemMode + 脆弱性感知

## 待完成
- [ ] 前端 Dashboard 重写（现代化 UI，Chart.js 图表）
- [ ] server.py 更新（对接 CognitiveOrchestrator）
- [ ] demo.py 更新
- [ ] 集成测试
