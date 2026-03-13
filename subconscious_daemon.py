#!/usr/bin/env python3
"""
GWS 潜意识守护进程 — 独立后台运行

不依赖 OpenClaw cron，自己管理周期循环。
通过文件与 Dashboard 通信（无额外依赖）。

Usage:
    python3 subconscious_daemon.py                    # 默认配置
    python3 subconscious_daemon.py --cycle 900        # 15分钟周期
    python3 subconscious-daemon.py --burst-agents 2   # 每次2个agent
    
通信:
    data/subconscious_stream.jsonl  — 潜意识活动流
    data/consciousness_stream.jsonl — 意识层输出流
    data/daemon_status.json         — 守护进程状态
"""

import argparse
import json
import signal
import sys
import time
from datetime import datetime
from pathlib import Path

# GWS 路径
sys.path.insert(0, str(Path(__file__).parent))
from core.gws import GWS


class SubconsciousDaemon:
    """潜意识守护进程"""

    def __init__(self, data_dir: str, cycle_seconds: int = 900, 
                 burst_agents: int = 2, llm: bool = False):
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.cycle_seconds = cycle_seconds
        self.running = False

        # 流文件
        self.sub_stream = self.data_dir / "subconscious_stream.jsonl"
        self.con_stream = self.data_dir / "consciousness_stream.jsonl"
        self.status_file = self.data_dir / "daemon_status.json"

        # 初始化 GWS
        self.gws = GWS(workspace_dir=str(self.data_dir))
        self.gws.start()
        
        if llm:
            config_path = Path(__file__).parent / "config" / "llm.json"
            if config_path.exists():
                cfg = json.loads(config_path.read_text())
                self.gws.enable_llm(
                    provider=cfg.get("provider", "openrouter"),
                    api_key=cfg.get("api_key", ""),
                    model=cfg.get("model", ""),
                )
                self._log("LLM 已启用")
        
        # 信号处理
        signal.signal(signal.SIGTERM, self._shutdown)
        signal.signal(signal.SIGINT, self._shutdown)

    def run(self):
        """主循环"""
        self.running = True
        self._log(f"守护进程启动 (周期: {self.cycle_seconds}s, agents: {self.gws.subconscious.burst_agents})")
        self._update_status("running")

        while self.running:
            try:
                cycle_start = time.time()
                self._run_cycle()
                
                # 等待下一个周期
                elapsed = time.time() - cycle_start
                sleep_time = max(10, self.cycle_seconds - elapsed)
                
                self._log(f"周期完成 ({elapsed:.0f}s)，{sleep_time:.0f}s 后继续")
                self._update_status("sleeping")
                
                # 分段 sleep 以便响应信号
                for _ in range(int(sleep_time / 5)):
                    if not self.running:
                        break
                    time.sleep(5)
                    
            except Exception as e:
                self._log(f"周期错误: {e}")
                time.sleep(60)

    def _run_cycle(self):
        """执行一个潜意识周期"""
        self._update_status("thinking")
        
        # 推进 GWS tick
        tick_result = self.gws.tick()
        
        # 收集潜意识产出
        sc_outputs = self.gws.subconscious.drain_outputs()
        
        for output in sc_outputs:
            entry = {
                "timestamp": datetime.now().isoformat(),
                "agent": output.agent_role.value,
                "content": output.content,
                "confidence": output.confidence,
                "emotion": output.emotion.to_dict(),
                "tags": output.tags,
            }
            self._append_stream(self.sub_stream, entry)

        # 收集意识层产出
        conscious = self.gws.get_output()
        if conscious:
            for item in conscious:
                entry = {
                    "timestamp": datetime.now().isoformat(),
                    "content": item.get("content", ""),
                    "thoughts": item.get("thoughts", []),
                    "agent_role": item.get("agent_role", ""),
                    "emotion": item.get("emotion", {}),
                    "evaluation": item.get("evaluation", 0),
                }
                self._append_stream(self.con_stream, entry)

        # 保存状态
        self.gws.save_state()

        # 记录周期摘要
        summary = {
            "timestamp": datetime.now().isoformat(),
            "subconscious_outputs": len(sc_outputs),
            "conscious_outputs": len(conscious) if conscious else 0,
            "emotion": self.gws.emotion_engine.state.label,
            "working_memory": len(self.gws.working_memory.get_all()),
            "long_term_memory": self.gws.long_term_memory.stats()["total"],
        }
        self._append_stream(self.sub_stream, {**summary, "type": "cycle_summary"})

    def _append_stream(self, filepath: Path, data: dict):
        """追加到 JSONL 流"""
        with open(filepath, "a") as f:
            f.write(json.dumps(data, ensure_ascii=False) + "\n")

    def _update_status(self, state: str):
        """更新守护进程状态"""
        status = {
            "state": state,
            "pid": __import__("os").getpid(),
            "cycle_seconds": self.cycle_seconds,
            "last_update": datetime.now().isoformat(),
            "emotion": self.gws.emotion_engine.state.label,
            "memory": self.gws.long_term_memory.stats()["total"],
            "uptime_ticks": self.gws._tick_count,
        }
        self.status_file.write_text(json.dumps(status, ensure_ascii=False, indent=2))

    def _log(self, msg: str):
        ts = datetime.now().strftime("%H:%M:%S")
        print(f"[{ts}] {msg}", flush=True)

    def _shutdown(self, *args):
        self._log("收到停止信号，正在关闭...")
        self.running = False
        self._update_status("stopped")
        self.gws.save_state()
        sys.exit(0)


def main():
    parser = argparse.ArgumentParser(description="GWS 潜意识守护进程")
    parser.add_argument("--data", default="./data", help="数据目录")
    parser.add_argument("--cycle", type=int, default=900, help="周期（秒），默认900=15分钟")
    parser.add_argument("--burst-agents", type=int, default=2, help="每次burst的agent数")
    parser.add_argument("--llm", action="store_true", help="启用LLM")
    args = parser.parse_args()

    daemon = SubconsciousDaemon(
        data_dir=args.data,
        cycle_seconds=args.cycle,
        burst_agents=args.burst_agents,
        llm=args.llm,
    )
    daemon.run()


if __name__ == "__main__":
    main()
