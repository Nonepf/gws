"""GWS 全局配置"""

# === 记忆层 ===
WORKING_MEMORY_CAPACITY = 20          # 工作记忆最大条目数
WORKING_MEMORY_HALF_LIFE = 1800       # 工作记忆半衰期（秒），30分钟
LONG_TERM_MEMORY_DECAY = 0.995        # 长期记忆每次访问的衰减系数
EMOTIONAL_BOOST_FACTOR = 1.5          # 高情绪唤醒时的记忆编码增强
MIN_MEMORY_STRENGTH = 0.05            # 低于此强度的记忆被遗忘

# === 情绪层 ===
EMOTION_DIMENSIONS = ["valence", "arousal", "dominance"]
EMOTION_DECAY_RATE = 0.98             # 情绪向自然中性衰减的速度

# === 潜意识层 ===
SUBCONSCIOUS_CYCLE_SECONDS = 3600     # 1小时大周期
SUBCONSCIOUS_BURST_AGENTS = 4         # burst期并行sub-agent数
SUBCONSCIOUS_BURST_DURATION = 1200    # burst期持续时间（秒），20分钟
