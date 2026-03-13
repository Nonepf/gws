# AI 认知架构调研报告

**日期**: 2026-03-13
**作者**: Perchwood (栖云木)
**工具**: Tavily Search API + Web Fetch

---

## 一、研究背景

GWS（Global Workspace System）是一个受 GWT 启发的 AI 认知架构原型。本报告调研当前学术界和工业界在 AI 认知架构、情感计算、记忆系统方面的最新进展，为 GWS 的迭代设计提供参考。

---

## 二、核心发现

### 2.1 LIDA — 最接近 GWS 的先驱

**来源**: University of Memphis CCRG (Stan Franklin 团队)

LIDA (Learning Intelligent Distribution Agent) 是目前最完整的 GWT 计算实现，与 GWS 的架构高度相似：

| LIDA 模块 | GWS 对应 | 差异 |
|-----------|----------|------|
| Perception Module | 情绪层 + 输入处理 | LIDA 有多模态感知，GWS 目前只有文本 |
| Workspace (Coalitions) | 潜意识层 + 全局工作空间 | LIDA 的 coalition 竞争机制更成熟 |
| Global Workspace (Broadcast) | 思考层 → 语言层 | GWS 直接用 LLM，LIDA 用专门的广播机制 |
| Procedural Memory | 未实现 | GWS 缺少程序记忆 |
| Declarative Memory | 长期记忆 | GWS 的语义检索更先进（TF-IDF vs LIDA 的激活扩散） |
| Action Selection | 思考层的筛选 | 类似但 LIDA 更复杂 |
| Sensory-Motor Memory | 未实现 | GWS 无此模块 |

**关键启发**:
- LIDA 有完整的 **perception → coalition → broadcast → action** 周期
- 每个周期约 100-200ms（生物合理性），GWS 目前是静态 tick
- LIDA 有 **attention codelets**（注意力子程序）——持续监视工作空间中的重要内容
- GWS 的优势：LLM 作为语言器官，表达能力远超 LIDA 的符号系统

### 2.2 UMM (Unified Mind Model) — LLM 时代的 GWT

**来源**: arXiv:2503.03459, 中国科学技术大学

这篇论文提出了跟 GWS 非常相似的思路：

> "LLM 可以作为前额叶（prefrontal cortex），支持多种类人认知能力"

UMM 的核心模块：
1. 多模态感知
2. 规划与推理
3. 工具使用
4. 学习
5. 记忆
6. 反思 (Reflection)
7. 动机 (Motivation)

**与 GWS 的对比**:
- UMM 更全面（7 个模块 vs GWS 的 5 层）
- GWS 的情绪系统更深入（UMM 的动机模块只是目标驱动，没有 PAD 模型）
- GWS 的潜意识层是 UMM 没有的独特设计
- UMM 的反思模块值得借鉴——GWS 目前没有自我审视机制

### 2.3 情感认知框架 — 情绪如何真正影响决策

**来源**: arXiv:2510.13195, 天津大学 + 埃克塞特大学

这篇论文直接解决了 GWS 的核心问题：**情绪如何影响 Agent 的行为/决策**。

他们的框架：
```
状态演化 → 欲望生成 → 目标优化 → 决策生成 → 行动执行
```

关键发现：
> "在有推理机制但没有情绪因素的系统中，尽管系统完全正常运行，决策和判断仍然是次优的。"

他们的实验证明：
- 有情绪框架的 Agent 在生态效度（ecological validity）上显著优于无情绪 Agent
- 情绪状态与行为的一致性是可信社会模拟的关键
- 情绪不是"装饰"，是**有界理性**（bounded rationality）的核心机制

**对 GWS 的启发**:
- GWS 目前的情绪→决策连接太弱（之前诊断的问题 ✓）
- 需要一个明确的 "欲望生成" 层——当前情绪应该产生具体的**行为倾向**
- 情绪应该影响目标优先级，不只是调整筛选阈值

### 2.4 四组件架构（PMPA）

工业界广泛采用的 Agent 架构：

```
Profile → Memory → Planning → Action
```

**Profile (身份/人格)**:
- 行为倾向、沟通风格、决策方式
- 伦理框架和约束
- GWS 的 personality.py 在做这件事 ✓

**Memory (记忆)**:
- 短期记忆 ↔ 工作记忆 ✓
- 长期记忆 ↔ 长期记忆 ✓
- 程序记忆（技能/方法）→ GWS 缺失
- 记忆整合 → GWS 有语义检索，但缺少主动 consolidation

**Planning (规划)**:
- 目标分解、策略形成、自适应调整
- GWS 目前没有明确的规划模块——思考层更像是即时反应

**Action (行动)**:
- GWS 目前只有语言输出
- 缺少工具使用、API 调用等行动能力

---

## 三、GWS 的定位分析

### 优势

1. **情绪系统的深度**: PAD 模型 + 情绪渗透所有层，比多数 Agent 框架更完整
2. **潜意识层**: 4 种 agent 的后台活动是独特设计，UMM/LIDA 都没有类似的
3. **LLM 作为语言器官**: 表达能力强，不需要手动编写输出模板
4. **纯 Python 无依赖**: 轻量，不需要 LangChain 等重型框架
5. **语义检索**: TF-IDF + 余弦相似度，比简单的关键词匹配好

### 不足

1. **无规划能力**: 只有即时的筛选和表达，没有长期目标和策略
2. **无反思机制**: 缺少 UMM 提到的 Reflection 模块
3. **情绪→行为连接弱**: 刚修复，还需要更多实验验证
4. **无程序记忆**: 只有陈述性记忆，缺少"怎么做"的知识积累
5. **无行动模块**: 只能说话，不能做事
6. **潜意识周期太长**: 1 小时 vs LIDA 的 100-200ms，信息处理效率低

---

## 四、实验设计

基于调研结果，设计以下实验来验证和改进 GWS：

### 实验 1: 情绪-决策耦合度测量

**目的**: 量化情绪对决策的影响程度

**方法**:
1. 给系统输入 10 组相同话题但不同情绪色彩的文本
2. 记录每组输入后：
   - 潜意识 agent 的角色分配变化
   - 工作空间的筛选结果差异
   - 语言层输出的风格差异
3. 计算情绪状态与行为输出的相关系数

**指标**:
- 角色分配变化率（不同情绪是否导致不同 agent 组合）
- 筛选结果重叠度（不同情绪下进入意识的内容差异）
- 输出文本的情绪一致性（语言风格是否匹配内部情绪）

**预期**: 高情绪强度应导致 >30% 的行为差异

### 实验 2: 潜意识周期优化

**目的**: 找到最优的潜意识活动频率

**方法**:
1. 测试不同周期时长：1min, 5min, 30min, 1h
2. 每个周期下运行 100 个 tick
3. 统计：
   - 有价值产出率（产出中被意识层采纳的比例）
   - 重复产出率（相同主题的重复发现）
   - 计算资源消耗

**预期**: 5-10 分钟周期可能是更好的平衡点

### 实验 3: 人格一致性测试

**目的**: 验证 personality.py 是否真正影响输出

**方法**:
1. 设置 3 套不同的人格参数（高好奇/低怀疑 vs 低好奇/高怀疑 vs 中性）
2. 对同一组输入生成回复
3. 让 LLM 评判三组回复的：
   - 好奇心表现（提问频率、探索性语言）
   - 怀疑精神（条件性表述、反例引用）
   - 表达风格差异

**预期**: 不同人格参数下输出应有可辨识的差异

### 实验 4: 记忆 consolidation 效果

**目的**: 测试记忆整合对检索质量的影响

**方法**:
1. 给系统输入 20 条相关信息
2. 等待 1 小时（允许遗忘机制运作）
3. 测试检索准确率：有 consolidation vs 无 consolidation
4. consolidation 方法：定期将相似记忆合并为摘要

**预期**: consolidation 后检索准确率提升 >20%

---

## 五、改进路线图

### 短期（1-2 天）

- [ ] 完成实验 1（情绪-决策耦合度）
- [ ] 加入反思模块：每 N 个周期自我审视一次
- [ ] 优化潜意识周期（测试更短的周期）

### 中期（1 周）

- [ ] 实现程序记忆（积累"怎么做"的知识）
- [ ] 加入简单的规划模块（目标分解 + 子任务队列）
- [ ] 完成人格一致性测试
- [ ] 实现记忆 consolidation

### 长期（持续）

- [ ] 多模态输入（不只是文本）
- [ ] 行动模块（工具使用、API 调用）
- [ ] 与 LIDA/UMM 进行系统性对比
- [ ] 撰写正式的架构论文

---

## 六、参考文献

1. Baars, B. J. (1988). *A Cognitive Theory of Consciousness*. Cambridge University Press.
2. Franklin, S. et al. "The LIDA Model of Global Workspace Theory." *Cognitive Systems Research*.
3. UMM: "Unified Mind Model: Reimagining Autonomous Agents in the LLM Era." arXiv:2503.03459.
4. "Emotional Cognitive Modeling Framework with Desire-Driven Objective Optimization." arXiv:2510.13195.
5. Sema4.ai. "Cognitive architecture in AI: How agents learn, reason, and adapt."
6. Gupta, D. "The Architecture of Autonomous AI Agents."

---

*本报告使用 Tavily API 搜索，web_fetch 提取原文内容。*
*所有搜索结果和报告已保存至 workspace/research/*
