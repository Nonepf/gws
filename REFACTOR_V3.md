# GWS v3 重构方案 — 情感驱动型认知智能体

## 背景

当前 GWS v2 (AWARE) 存在以下核心问题：
- 情绪系统仅是 PAD 混合，缺乏 OCC 认知评估理论支撑
- 内驱力是简单的水位线模型，未实现稳态强化学习 (HRRL)
- 缺乏神经递质模拟（多巴胺/血清素/皮质醇）
- 记忆系统有情绪字段但没有真正的躯体标记 (Somatic Markers)
- 全局工作空间缺乏显著性竞争与"点火"机制
- 多个 EmotionState 类定义冗余（memory.py 和 emotion.py 各一个）
- 前端简陋（710行单文件HTML，无响应式设计，图表粗糙）
- 后端 Bug：JSON 序列化 UTF-8 surrogate 问题、状态恢复不健壮、LLM 无重试

## 重构目标

实现一篇认知科学论文级别的严谨架构：
1. **OCC 评估层** — 基于事件/行动/对象的结构化情感评估
2. **稳态内驱力 (HRRL)** — 数学建模的驱动函数 d(H_t) + 主奖励 = 驱动力减少
3. **神经递质模拟** — DA/5-HT/Cortisol 作为认知调制因子
4. **躯体标记记忆** — 每条记忆带 PAD 向量，检索时利用情感印记加速决策
5. **GWT 点火机制** — 显著性竞争 + 阈值点火 + 全局广播
6. **有界自治** — 稳态目标防止无限优化
7. **现代化前端** — 响应式 Dashboard，实时图表，情绪可视化

## 新架构

```
┌─────────────────────────────────────────────┐
│              用户交互 / Web Dashboard          │
├─────────────────────────────────────────────┤
│              语言层 (LLM Output)              │
├─────────────────────────────────────────────┤
│          全局工作空间 (GW) — 思考层             │
│  ┌──────────────────────────────────────┐   │
│  │ 显著性竞争 → 阈值点火 → 全局广播       │   │
│  └──────────────────────────────────────┘   │
├─────────────────────────────────────────────┤
│           OCC 评估层 (情感产生)                │
│  事件后果评估 │ 行动规范评估 │ 对象吸引力评估    │
├─────────────────────────────────────────────┤
│        PAD 心境缓冲器 + 神经递质调制            │
├─────────────────────────────────────────────┤
│     潜意识层 (4 Agent 并行)                    │
│  Explorer │ Pattern │ Associator │ Dreamer   │
├─────────────────────────────────────────────┤
│        稳态内驱力 (HRRL)                       │
│  d(H_t) = Σ|h* - h|  → 驱动力减少 = 奖励      │
├─────────────────────────────────────────────┤
│      记忆层 (情感标注 + 躯体标记)               │
│  工作记忆 │ 长期记忆 │ 语义检索 │ 遗忘          │
├─────────────────────────────────────────────┤
│      状态持久化 + 有界自治 + 安全对齐           │
└─────────────────────────────────────────────┘
```

## 文件结构 (v3)

```
gws/
├── core/
│   ├── __init__.py
│   ├── orchestrator.py      # 主协调器 (替代 gws.py 的 AWARE 类)
│   ├── occ.py              # NEW: OCC 认知评估引擎
│   ├── emotion.py          # REWRITE: PAD 心境缓冲器 + 神经递质
│   ├── drives.py           # REWRITE: 稳态内驱力 HRRL
│   ├── workspace.py        # REWRITE: GWT 点火机制
│   ├── memory.py           # REWRITE: 躯体标记 + 情感标注
│   ├── subconscious.py     # REFACTOR: 增强情感调制
│   ├── retrieval.py        # ENHANCE: 加入躯体标记检索
│   ├── neurotransmitter.py # NEW: 神经递质模拟
│   ├── language.py         # REFACTOR: 整合新情绪系统
│   ├── llm.py             # ENHANCE: 重试 + 限流
│   ├── events.py          # KEEP: 事件总线（基本不变）
│   ├── blackboard.py       # ENHANCE: 显著性竞争 + 点火
│   ├── intentions.py       # REFACTOR: 对接 HRRL
│   ├── state.py           # REWRITE: 完整 v3 状态保存
│   ├── safety.py          # NEW: 有界自治 + 安全对齐
│   └── bridge.py          # KEEP: OpenClaw 桥接
├── config/
│   ├── personality.py      # ENHANCE: 更多情绪表达
│   ├── settings.py         # REWRITE: v3 配置
│   └── llm.json.example
├── web/
│   ├── index.html          # REWRITE: 现代化 Dashboard
│   ├── css/
│   │   └── dashboard.css   # NEW: 独立样式
│   └── js/
│       └── dashboard.js    # NEW: 独立 JS + Chart.js
├── server.py               # REWRITE: FastAPI 替代手写 HTTP
├── demo.py                 # UPDATE: v3 demo
├── conversation.py         # UPDATE: v3 对话
└── requirements.txt        # NEW: 依赖清单
```

## 核心模块详细设计

### 1. OCC 评估层 (core/occ.py) — NEW

```python
class AppraisalDimension(Enum):
    GOAL_RELEVANCE = "goal_relevance"       # 事件是否与目标相关
    GOAL_CONGRUENCE = "goal_congruence"     # 事件是否有利
    EXPECTATION_CONFIRMATION = "expectation" # 是否符合预期
    AGENCY = "agency"                        # 谁导致的（自己/他人/环境）
    NORM_CONSISTENCY = "norm_consistency"    # 是否符合规范
    ATTRACTIVENESS = "attractiveness"        # 对象吸引力

@dataclass
class AppraisalResult:
    dimensions: dict[AppraisalDimension, float]
    emotion_category: EmotionCategory  # 22种OCC情感
    intensity: float
    pad_vector: EmotionState           # 映射到 PAD

class OCCEngine:
    def appraise_event(self, event, goals, expectations) -> AppraisalResult
    def appraise_action(self, action, standards, agent) -> AppraisalResult  
    def appraise_object(self, object, attitudes) -> AppraisalResult
    def to_pad(self, occ_result) -> EmotionState  # OCC → PAD 映射
```

### 2. 神经递质模拟 (core/neurotransmitter.py) — NEW

```python
@dataclass
class NeurotransmitterState:
    dopamine: float = 0.5       # 奖励预测误差、动力 [0, 1]
    serotonin: float = 0.5      # 冲动控制、情绪稳定 [0, 1]
    cortisol: float = 0.2       # 压力响应 [0, 1]

    def modulate_learning_rate(self, base_lr) -> float:
        # 多巴胺调节学习率
        return base_lr * (0.5 + self.dopamine)

    def modulate_discount(self, base_gamma) -> float:
        # 血清素调节时间折扣
        return base_gamma * (0.7 + self.serotonin * 0.3)

    def modulate_temperature(self, base_temp) -> float:
        # 皮质醇调节动作采样温度（压力→更冲动/更保守）
        return base_temp * (1.0 + self.cortisol * 0.5)
```

### 3. 稳态内驱力 HRRL (core/drives.py) — REWRITE

```python
@dataclass
class HomeostaticState:
    # 多维稳态空间 H
    energy: float = 0.5           # 能量水平
    information: float = 0.5      # 信息充足度
    coherence: float = 0.5        # 认知一致性
    social: float = 0.5           # 社交连接度
    safety: float = 0.8           # 安全感

    # 设定点 H*
    setpoints: dict = {
        "energy": 0.7,
        "information": 0.6,
        "coherence": 0.7,
        "social": 0.5,
        "safety": 0.8,
    }

class HRRLDriveEngine:
    def drive(self, H_t, m=2) -> float:
        """d(H_t) = (Σ|h* - h|^m)^(1/m)"""
        deviations = [abs(H_t.setpoints[k] - getattr(H_t, k)) 
                      for k in H_t.setpoints]
        return (sum(d**m for d in deviations) ** (1/m))

    def primary_reward(self, H_before, H_after, K_t) -> float:
        """r(H_t, K_t) = d(H_before) - d(H_after)"""
        return self.drive(H_before) - self.drive(H_after)
```

### 4. 躯体标记记忆 (core/memory.py) — REWRITE

每条记忆带 PAD 向量（情感印记），检索时利用躯体标记加速：
- 正向标记 → 优先考虑该路径
- 负向标记 → 提前抑制

### 5. GWT 点火机制 (core/workspace.py) — REWRITE

```python
class GlobalWorkspace:
    def salience_competition(self, entries):
        """显著性竞争：考虑当前心境 + 驱动状态"""
        for entry in entries:
            entry.salience = self._compute_salience(entry)

    def ignition(self, winner):
        """全局点火：占领中央缓冲区，广播给所有模块"""
        self.conscious_buffer = winner
        self._broadcast(winner)

    def _compute_salience(self, entry):
        """显著性 = f(内容强度, 情绪共鸣, 驱动相关性, 新奇度)"""
```

### 6. 有界自治 (core/safety.py) — NEW

```python
class BoundedAutonomy:
    """稳态智能体追求平衡点，而非无限优化"""
    def check_bounds(self, action, homeostatic_state):
        # 安全维度偏离 → 阻止
        # 资源消耗过高 → 限制
        # 稳态已满足 → 进入待机
```

## 前端重构

- Vue 3 + Chart.js / ECharts（或纯原生，保持零依赖）
- 响应式布局（移动端适配）
- 实时情绪雷达图
- 内驱力仪表盘
- 潜意识活动时间线
- 记忆可视化（情感强度热图）
- 对话界面改进

## 后端 Bug 修复

1. `memory.py`: 统一 EmotionState，消除重复定义
2. `llm.py`: 添加重试逻辑 + 速率限制
3. `state.py`: 健壮的状态恢复（异常处理、版本迁移）
4. JSON 序列化: 使用 `ensure_ascii=False, errors='replace'` 统一处理
5. `subconscious.py`: 修复离线模式下的模板化输出

## 实施优先级

**Phase 1 — 核心重构（ACP Agent 执行）**
1. 创建新模块骨架（occ.py, neurotransmitter.py, safety.py）
2. 重写 emotion.py（PAD 缓冲器 + 神经递质集成）
3. 重写 drives.py（HRRL 稳态模型）
4. 重写 memory.py（躯体标记 + 统一 EmotionState）
5. 重写 workspace.py（GWT 点火机制）
6. 增强 blackboard.py（显著性竞争）
7. 重构 orchestrator.py（整合所有新模块）
8. 修复已知 Bug

**Phase 2 — 前端 + 集成**
9. 前端 Dashboard 重写
10. server.py 重写（API 对接新架构）
11. 集成测试 + demo.py 更新

**Phase 3 — 精调**
12. 性格配置更新
13. 状态持久化 v3
14. 文档更新

## 测试策略

- 每个模块独立单元测试
- 集成测试：完整认知循环
- 离线模式验证（无 LLM 也能产生有意义输出）
- 情绪传播测试：输入 → OCC → PAD → 驱动力 → 记忆编码 → 检索
