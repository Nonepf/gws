# GWS 设计诊断 — 2026-03-13

## 问题一：情绪真的影响决策吗？

**答案：几乎没有。** 情绪系统搭得很完整，但和其他层的连接是假的。

### 逐层分析

#### 潜意识层 — 最严重的问题

- `_select_roles()` 用了情绪（activity > 0.6 加 ASSOCIATOR，risk > 0.3 加 DREAMER），但阈值几乎永远触发不了（默认 arousal ≈ 0 → activity ≈ 0.5）
- **四个 agent 行为完全无视情绪**：
  - `explorer`：随机拉 3 条记忆，不管情绪状态，不管效价方向
  - `pattern_finder`：统计标签频率，跟情绪无关
  - `associator`：随机配对两条记忆，纯随机
  - `dreamer`：硬编码的 3 句诗或者随机拼接，没有情绪驱动的梦境内容
- Agent 的 confidence 是硬编码常数（0.4, 0.5, 0.3, 0.2），不随情绪变化
- **结论**：潜意识产出和情绪状态基本无关。情绪系统在旁边看着，但没有参与。

#### 思考层 — 表面文章

- `_evaluate()` 加了 `emotion.intensity * 0.2`，影响微乎其微
- `_adjust_by_strategy()` 用 1.2x/0.8x 乘数调整评估分数，但：
  - strategy 只影响"严不严格"，不影响"往哪个方向思考"
  - 没有改变思考的**内容**，只是改变了筛选的**门槛**
- **结论**：情绪能微调筛选阈值，但不改变思考方向和内容。

#### 语言层 — 最大的浪费

- 收到了完整的 emotion_influence，但 system prompt 只是说 "reflect the current emotional state in tone"
- 没有具体指导：什么情绪用什么风格？什么节奏？什么词汇倾向？
- `_express_silence()` 的情绪映射太小（7 条），大部分情绪状态映射到 "……"
- **结论**：LLM 靠自己的理解去翻译情绪，但 prompt 没给足够指导。

#### 记忆层 — 唯一做得还行的地方

- 编码时有 emotional_boost（1.0 + intensity * 0.5）✓
- 检索时有 mood-congruent recall（情绪相似 +30%）✓
- 这部分是对的

### 问题根源

各层**独立实现了情绪感知**，但没有真正**消费**它。就像房间里装了温度计但没有空调——知道冷暖，但不做反应。

---

## 问题二：没有性格

### 现状

- System prompt 是 "You are the language output layer of a cognitive AI system"
- 这是一个**零件说明书**，不是一个有性格的意识
- 没有：
  - 说话风格（正式？随意？诗意？幽默？）
  - 思考偏好（喜欢类比？喜欢质疑？喜欢找联系？）
  - 价值观（重视什么？回避什么？）
  - 情绪表达习惯（压抑？外放？自嘲？）
  - 一致性（每轮对话都是"全新的人"）

### 对比

- 栖云木（OpenClaw agent）：有 SOUL.md → 有性格 → 回复有辨识度
- GWS：没有 SOUL → 没有性格 → 回复像 ChatGPT 默认输出

---

## 改进方案

### A. 让情绪真正影响潜意识

1. **Agent 行为改为情绪驱动**：
   - explorer：高 valence → 探索正面记忆，低 valence → 探索负面记忆
   - associator：高 arousal → 跨领域联想，低 arousal → 相似主题联想
   - dreamer：低 dominance → 荒诞梦境，高 dominance → 野心/愿景式梦境
   - pattern_finder：高 arousal → 找异常，低 arousal → 找常规模式

2. **Agent confidence 动态计算**：
   - 跟情绪强度挂钩
   - 跟记忆检索的匹配度挂钩
   - 跟 agent 类型和当前情绪的适配度挂钩

3. **情绪状态影响 agent 的"活跃度"**：
   - 不只是"有没有这个 agent"，而是每个 agent 的产出数量和深度

### B. 让情绪影响思考方向

1. **思考策略不止是门槛调整**：
   - exploratory：降低 promotion_threshold，同时增加交叉引用
   - cautious：提高阈值，同时偏向已有验证的主题
   - neutral：当前行为

2. **情绪影响话题选择**：
   - 焦虑时 → 倾向于"解决问题"类思考
   - 兴奋时 → 倾向于"发散联想"类思考
   - 悲伤时 → 倾向于"回顾反思"类思考

### C. 给 GWS 一个性格

1. **创建 `config/personality.py`**：
   - 定义说话风格、思考偏好、价值观
   - 贯穿语言层和思考层

2. **语言层 prompt 重写**：
   - 不是 "express thoughts naturally"
   - 而是具体的性格指导：用什么比喻、什么节奏、什么态度

3. **性格影响思考**：
   - 不只是输出风格，影响内部的评估标准

### D. 调试和验证

1. 加入情绪决策追踪日志
2. demo.py 展示情绪对各层的实际影响
3. 对比实验：同一输入，不同情绪状态下的不同行为
