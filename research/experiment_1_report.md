# 实验 1: 情绪-决策耦合度测量

**日期**: 2026-03-13
**状态**: ✅ 完成

## 实验目的

量化情绪对 GWS 各层决策的实际影响。

## 方法

5 组输入 × 3 个样本，每组不同情绪色彩：
- positive_high: "太棒了！" "兴奋得不行！" "完美！"
- positive_low: "挺有意思的" "还不错" "踏实"
- negative_high: "完了完了！" "焦虑得不行！" "太糟糕了！"
- negative_low: "唉，失败了" "有点难过" "累了"
- neutral: "天气不错" "O(n log n)" "检查日志"

## 关键发现

### 1. 思考策略分化 ✓

| 情绪组 | 策略 |
|--------|------|
| positive_high | {neutral, **exploratory**} |
| negative_high | {neutral, **cautious**} |
| neutral | {neutral} |

正向情绪 → 探索模式（降低筛选门槛，发散思考）
负向情绪 → 谨慎模式（提高筛选门槛，收敛思考）

### 2. 意识提升量差异 ✓

| 情绪组 | 平均意识提升/轮 |
|--------|----------------|
| positive_high | **3.0** |
| negative_high | **2.7** |
| positive_low | 2.3 |
| negative_low | 2.0 |
| neutral | 1.0 |

高唤醒状态（无论正负）产生更多意识内容。
正向比负向多 11%（3.0 vs 2.7）。

### 3. 角色分配未分化 ✗

所有组都使用 [explorer, pattern_finder, associator]。
dreamer 未被激活，因为 dominance 值未超过 0.3 阈值。

**可能的改进**: 降低 dreamer 的 dominance 阈值，或增加 dominance 的提取权重。

### 4. 情绪提取器修复前后的对比

| 版本 | V 值范围 | 策略分化 | 意识提升差异 |
|------|---------|---------|------------|
| 修复前（平均化） | -0.09 ~ +0.13 | 无（全是 neutral） | 无 |
| 修复后（权重+放大） | -0.18 ~ +0.19 | 有（exploratory/cautious） | 3x |

修复内容：
1. 长词权重更高（更具体的表达）
2. 信号放大系数 1.5x
3. 不再除以匹配次数，改为加权平均

## 数据文件

详细结果: `research/experiment_1_results.json`
