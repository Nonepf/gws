#!/usr/bin/env python3
"""
GWS 潜意识 Cron Agent

由 OpenClaw cron 定期调用（每 15-30 分钟），
推进 GWS 的潜意识周期，产出写入记忆文件。

用法（由 cron 调用）：
    python3 gws/cron_agent.py

功能：
1. 加载 GWS 状态
2. 推进潜意识 tick
3. 如果有高价值产出，写入 memory/YYYY-MM-DD.md
4. 保存状态
"""

import json
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from core.gws import GWS


def main():
    # 确保从正确的工作目录运行
    workspace = Path("/home/nonepf/.openclaw/workspace")
    gws_data = workspace / "gws" / "data"
    sys.path.insert(0, str(workspace / "gws"))

    # 加载 LLM 配置
    llm_config_path = Path(__file__).parent / "config" / "llm.json"
    if llm_config_path.exists():
        llm_cfg = json.loads(llm_config_path.read_text())
    else:
        llm_cfg = None

    # 初始化 GWS
    gws = GWS(workspace_dir=str(gws_data))
    if llm_cfg:
        gws.enable_llm(
            provider=llm_cfg.get("provider", "openrouter"),
            api_key=llm_cfg.get("api_key", ""),
            model=llm_cfg.get("model", ""),
        )
    gws.start()

    # 推进 3 个 tick（模拟潜意识活动）
    insights = []
    for _ in range(3):
        result = gws.tick()
        if result["new_conscious"] > 0:
            conscious = gws.get_output()
            if conscious:
                for item in conscious:
                    if item.get("evaluation", 0) > 0.5:
                        insights.append(item)

    # 筛选有价值的洞察（去重 + 过滤自指）
    significant = []
    seen_content = set()
    for insight in insights:
        content = insight.get("content", "")
        # 跳过重复内容
        key = content[:50]
        if key in seen_content:
            continue
        seen_content.add(key)
        # 跳过纯自指（只在说自己的内部标签）
        if "workspace" in content and "promoted" in content and len(content) < 60:
            continue
        # 跳过太短的
        if len(content) < 15:
            continue
        significant.append(insight)

    # 如果有洞察，写入今日记忆
    if significant:
        today = datetime.now().strftime("%Y-%m-%d")
        memory_file = workspace / "memory" / f"{today}.md"

        entry_lines = ["\n## 🌊 GWS 潜意识活动\n"]
        for insight in significant[:3]:  # 最多3条
            content = insight.get("content", "")
            role = insight.get("agent_role", "unknown")
            entry_lines.append(f"- [{role}] {content[:120]}")

        # 情绪状态
        emotion = gws.emotion_engine.get_influence()
        entry_lines.append(f"- 情绪: {emotion['label']} (强度={emotion['intensity']:.2f})")

        entry = "\n".join(entry_lines) + "\n"

        with open(memory_file, "a", encoding="utf-8") as f:
            f.write(entry)

        print(f"Wrote {len(significant)} insights to {memory_file}")
    else:
        print("No significant insights this cycle")

    # 输出状态
    status = gws.get_status()
    print(json.dumps(status, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
