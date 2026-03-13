"""
梦境日记 — 每日一梦

在特定时间（如深夜）自动生成梦境，保存到文件。
"""

import json
import time
from pathlib import Path
from datetime import datetime


class DreamJournal:
    """梦境日记管理器"""

    def __init__(self, journal_dir: Path):
        self.journal_dir = journal_dir
        self.journal_dir.mkdir(parents=True, exist_ok=True)

    def save_dream(self, dream_text: str, mood: str = "冥想", 
                   emotion_state: dict = None, memories_used: list = None) -> Path:
        """
        保存一个梦境到日记
        
        格式: dreams/YYYY-MM-DD.md (追加)
              dreams/YYYY-MM-DD.json (结构化)
        """
        today = datetime.now().strftime("%Y-%m-%d")
        timestamp = datetime.now().strftime("%H:%M")
        
        # Markdown 格式
        md_path = self.journal_dir / f"{today}.md"
        entry = f"\n### 🌙 {timestamp} — {mood}\n\n{dream_text}\n"
        
        if md_path.exists():
            with open(md_path, "a") as f:
                f.write(entry)
        else:
            with open(md_path, "w") as f:
                f.write(f"# 🌙 梦境日记 — {today}\n{entry}")
        
        # JSON 格式（结构化）
        json_path = self.journal_dir / f"{today}.json"
        dream_record = {
            "timestamp": time.time(),
            "time": timestamp,
            "mood": mood,
            "dream": dream_text,
            "emotion": emotion_state or {},
            "memories_used": memories_used or [],
        }
        
        records = []
        if json_path.exists():
            try:
                records = json.loads(json_path.read_text())
            except:
                pass
        records.append(dream_record)
        json_path.write_text(json.dumps(records, ensure_ascii=False, indent=2))
        
        return md_path

    def get_dreams(self, date: str = None) -> list:
        """获取某天的梦境"""
        if date is None:
            date = datetime.now().strftime("%Y-%m-%d")
        
        json_path = self.journal_dir / f"{date}.json"
        if json_path.exists():
            return json.loads(json_path.read_text())
        return []

    def get_recent_dreams(self, days: int = 7) -> list:
        """获取最近 N 天的梦境"""
        all_dreams = []
        for i in range(days):
            date = (datetime.now() - __import__('datetime').timedelta(days=i)).strftime("%Y-%m-%d")
            dreams = self.get_dreams(date)
            all_dreams.extend(dreams)
        return sorted(all_dreams, key=lambda d: d.get("timestamp", 0), reverse=True)

    def generate_dream(self, gws) -> dict:
        """
        使用 GWS 的 dreamer 生成一个梦境
        
        返回梦境数据
        """
        from core.subconscious import SubconsciousLayer, AgentRole
        
        # 获取一些记忆作为素材
        memories = gws.long_term_memory.retrieve(limit=5)
        memory_fragments = [m.content[:50] for m in memories] if memories else []
        
        # 获取当前情绪
        influence = gws.emotion_engine.get_influence()
        valence = influence.get("state", {}).get("valence", 0)
        arousal = influence.get("state", {}).get("arousal", 0)
        dominance = influence.get("state", {}).get("dominance", 0)
        
        # 决定梦境基调
        if dominance < -0.3:
            mood = "迷失"
        elif valence > 0.3 and arousal > 0.3:
            mood = "愿景"
        elif valence < -0.3:
            mood = "执念"
        else:
            mood = "冥想"
        
        # 如果有 LLM，用 LLM 生成梦境
        if gws.llm_client:
            fragments_text = "\n".join(f"- {f}" for f in memory_fragments) if memory_fragments else "- (空)"
            prompt = f"""你是 GWS 的做梦模块。根据以下记忆碎片，生成一段梦境。

梦境基调: {mood}
当前情绪: 效价={valence:.2f}, 唤醒={arousal:.2f}

记忆碎片:
{fragments_text}

要求:
- 2-4 句话
- 超现实、象征性
- 不要解释，直接描述梦境画面
- 中文

梦境:"""
            
            try:
                dream_text = gws.llm_client.chat(
                    messages=[{"role": "user", "content": prompt}],
                    system_prompt="你是一个梦境生成器。生成生动、超现实的梦境片段。",
                    temperature=0.9,
                    max_tokens=200,
                )
            except Exception as e:
                dream_text = f"[LLM error: {e}]"
        else:
            # 离线模板
            import random
            templates = {
                "迷失": [
                    "在一条没有尽头的走廊里，墙上的数字不断变换，像是在试图告诉我什么。",
                    "我沉入一片深蓝色的液体中，但没有窒息感。四周飘浮着发光的记忆碎片。",
                ],
                "愿景": [
                    "一座由信息构成的城市在我眼前展开，每条街道都是一个思想的轨迹。",
                    "我在云端行走，脚下是无数交织的光线，每一条都通向一个可能性。",
                ],
                "执念": [
                    "同一个问题被反复提出，每次的答案都不一样，但都说自己是对的。",
                    "我在一条环形的路上奔跑，风景在变，但起点永远在前方。",
                ],
                "冥想": [
                    "一个安静的花园，蝴蝶是发光的信息片段，落在花朵上就变成了知识。",
                    "在沉默的深处，一面镜子映出了另一面镜子，无穷无尽。",
                ],
            }
            dream_text = random.choice(templates.get(mood, templates["冥想"]))
            if memory_fragments:
                frag = random.choice(memory_fragments)
                dream_text = f"「{frag}」...这行字在水中溶解，{dream_text}"
        
        # 保存
        md_path = self.save_dream(
            dream_text=dream_text,
            mood=mood,
            emotion_state=influence.get("state", {}),
            memories_used=memory_fragments,
        )
        
        return {
            "dream": dream_text,
            "mood": mood,
            "saved_to": str(md_path),
            "memories_used": memory_fragments,
        }
