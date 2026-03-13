#!/usr/bin/env python3
"""
GWS Dashboard — 异步 Web 服务器

输入不阻塞，LLM 后台处理，前端轮询获取回复。
"""

import argparse
import json
import sys
import threading
import time
import uuid
from datetime import datetime
from http.server import HTTPServer, SimpleHTTPRequestHandler
from pathlib import Path

gws_instance = None
chat_history = []
chat_history_file = None

# 异步任务队列
tasks = {}  # task_id -> {status, result}
tasks_lock = threading.Lock()


class GWSHandler(SimpleHTTPRequestHandler):
    def do_GET(self):
        path = self.path.split('?')[0]
        routes = {
            '/': self._serve_index,
            '/api/status': self._api_status,
            '/api/history': self._api_history,
            '/api/memory': self._api_memory,
            '/api/subconscious': self._api_subconscious,
            '/api/consciousness': self._api_consciousness,
            '/api/daemon': self._api_daemon,
            '/api/task': self._api_task,
        }
        handler = routes.get(path)
        if handler:
            handler()
        else:
            self.send_error(404)

    def do_POST(self):
        routes = {
            '/api/input': self._api_input,
            '/api/tick': self._api_tick,
        }
        handler = routes.get(self.path)
        if handler:
            handler()
        else:
            self.send_error(404)

    def _serve_index(self):
        path = Path(__file__).parent / 'web' / 'dashboard.html'
        if path.exists():
            self.send_response(200)
            self.send_header('Content-Type', 'text/html; charset=utf-8')
            self.end_headers()
            self.wfile.write(path.read_bytes())
        else:
            self.send_error(404)

    def _json(self, data, status=200):
        body = json.dumps(data, ensure_ascii=False, default=str).encode()
        self.send_response(status)
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Content-Length', len(body))
        self.end_headers()
        self.wfile.write(body)

    def _read_body(self):
        length = int(self.headers.get('Content-Length', 0))
        return json.loads(self.rfile.read(length)) if length else {}

    # === API ===

    def _api_status(self):
        if gws_instance:
            self._json(gws_instance.get_status())
        else:
            self._json({"error": "not initialized"})

    def _api_history(self):
        self._json({"history": chat_history[-50:]})

    def _api_memory(self):
        if gws_instance:
            wm = [{"content": e.content[:100], "strength": round(e.strength, 2)}
                  for e in gws_instance.working_memory.get_all()]
            ltm_e = gws_instance.long_term_memory.retrieve(limit=30)
            ltm = [{"content": e.content[:100], "type": e.memory_type.value,
                    "strength": round(e.strength, 2), "tags": e.tags[:3]} for e in ltm_e]
            self._json({"working_memory": wm, "long_term_memory": ltm})
        else:
            self._json({"working_memory": [], "long_term_memory": []})

    def _api_subconscious(self):
        data_dir = Path(gws_instance.workspace_dir) if gws_instance else Path("./data")
        entries = _read_jsonl(data_dir / "subconscious_stream.jsonl", limit=50)
        self._json({"entries": entries})

    def _api_consciousness(self):
        data_dir = Path(gws_instance.workspace_dir) if gws_instance else Path("./data")
        entries = _read_jsonl(data_dir / "consciousness_stream.jsonl", limit=20)
        self._json({"entries": entries})

    def _api_daemon(self):
        data_dir = Path(gws_instance.workspace_dir) if gws_instance else Path("./data")
        sf = data_dir / "daemon_status.json"
        if sf.exists():
            self._json(json.loads(sf.read_text()))
        else:
            self._json({"state": "not_running"})

    def _api_task(self):
        """查询任务状态: /api/task?id=xxx"""
        from urllib.parse import parse_qs, urlparse
        params = parse_qs(urlparse(self.path).query)
        task_id = params.get('id', [''])[0]
        with tasks_lock:
            task = tasks.get(task_id)
        if task:
            self._json(task)
        else:
            self._json({"error": "task not found"}, 404)

    def _api_input(self):
        """异步处理输入 - 立即返回 task_id"""
        try:
            data = self._read_body()
            text = data.get('text', '')
        except:
            self._json({"error": "Invalid JSON"}, 400)
            return

        if not gws_instance:
            self._json({"error": "GWS not initialized"}, 503)
            return

        # 创建任务
        task_id = str(uuid.uuid4())[:8]
        with tasks_lock:
            tasks[task_id] = {"status": "processing", "text": text}

        # 立即返回，后台处理
        self._json({"task_id": task_id, "status": "processing"})

        # 后台线程处理 LLM
        t = threading.Thread(target=_process_input, args=(task_id, text), daemon=True)
        t.start()

    def _api_tick(self):
        if not gws_instance:
            self._json({"error": "GWS not initialized"}, 503)
            return
        action = gws_instance.autonomous_tick()
        gws_instance.save_state()
        self._json(action)

    def log_message(self, format, *args):
        pass


def _process_input(task_id: str, text: str):
    """后台处理用户输入"""
    global chat_history

    try:
        # 1. 处理输入（情绪、记忆）
        result = gws_instance.on_input(text)

        # 2. 捕获潜意识产出
        sc_outputs = gws_instance.subconscious.drain_outputs()
        sc_entries = []
        for out in sc_outputs:
            entry = {
                "role": out.agent_role.value,
                "content": out.content[:300],
                "confidence": round(out.confidence, 2),
                "time": datetime.now().isoformat(),
            }
            sc_entries.append(entry)
            _append_stream(gws_instance.workspace_dir / "subconscious_stream.jsonl", entry)

        # 3. 意识层产出
        conscious = gws_instance.get_output() or []
        for item in conscious:
            entry = {
                "content": item.get("content", "")[:300],
                "agent_role": item.get("agent_role", ""),
                "time": datetime.now().isoformat(),
            }
            _append_stream(gws_instance.workspace_dir / "consciousness_stream.jsonl", entry)

        # 4. LLM 回复（不用 speak() 避免重复 on_input）
        response_text = None
        if gws_instance.language_layer:
            try:
                # 直接调用语言层，不经过 speak()（speak 会重复 on_input）
                conscious = gws_instance.workspace.get_consciousness()
                influence = gws_instance.emotion_engine.get_influence()
                memories = gws_instance.long_term_memory.retrieve(
                    query=text, emotion_bias=gws_instance.emotion_engine.state, limit=3,
                )
                memory_context = [m.content for m in memories]
                response_text = gws_instance.language_layer.respond_to_user(
                    user_message=text,
                    conscious_outputs=conscious,
                    emotion_influence=influence,
                    memory_context=memory_context,
                )
            except Exception as e:
                response_text = f"[回复失败: {e}]"

        gws_instance.save_state()

        # 5. 更新聊天历史
        chat_history.append({"role": "user", "text": text, "time": time.time()})
        if response_text:
            chat_history.append({"role": "gws", "text": response_text, "time": time.time(),
                                "emotion": result.get("emotion_label", "")})
        _save_chat()

        # 6. 完成任务
        with tasks_lock:
            tasks[task_id] = {
                "status": "done",
                "response": response_text,
                "emotion": result.get("emotion_label", ""),
                "subconscious": sc_entries,
                "consciousness": [c.get("content", "")[:200] for c in conscious],
                "has_llm": gws_instance.language_layer is not None,
            }
    except Exception as e:
        with tasks_lock:
            tasks[task_id] = {"status": "error", "error": str(e)}


# === Helpers ===

def _read_jsonl(path: Path, limit=50):
    if not path.exists():
        return []
    lines = path.read_text().strip().split('\n')
    out = []
    for l in lines[-limit:]:
        try:
            out.append(json.loads(l))
        except:
            pass
    return out


def _append_stream(path: Path, data: dict):
    with open(path, "a") as f:
        f.write(json.dumps(data, ensure_ascii=False) + "\n")


def _save_chat():
    if chat_history_file:
        chat_history_file.write_text(json.dumps(chat_history[-100:], ensure_ascii=False, indent=2))


def _load_chat():
    global chat_history
    if chat_history_file and chat_history_file.exists():
        try:
            chat_history = json.loads(chat_history_file.read_text())
        except:
            chat_history = []


def auto_tick_loop(interval):
    while True:
        time.sleep(interval)
        if gws_instance:
            try:
                gws_instance.autonomous_tick()
                gws_instance.save_state()
            except Exception as e:
                print(f"[tick] {e}")


def main():
    global gws_instance, chat_history_file

    parser = argparse.ArgumentParser()
    parser.add_argument('--port', type=int, default=8080)
    parser.add_argument('--host', default='127.0.0.1')
    parser.add_argument('--with-gws', action='store_true')
    parser.add_argument('--gws-data', default='./data')
    parser.add_argument('--llm', action='store_true')
    parser.add_argument('--auto-tick', type=int, default=0)
    args = parser.parse_args()

    if args.with_gws:
        sys.path.insert(0, str(Path(__file__).parent))
        from core.gws import GWS

        gws_instance = GWS(workspace_dir=args.gws_data)
        gws_instance.start()
        chat_history_file = gws_instance.workspace_dir / "chat_history.json"
        _load_chat()

        if args.llm:
            cfg_path = Path(__file__).parent / 'config' / 'llm.json'
            if cfg_path.exists():
                cfg = json.loads(cfg_path.read_text())
                gws_instance.enable_llm(provider=cfg.get('provider',''), 
                                       api_key=cfg.get('api_key',''), 
                                       model=cfg.get('model',''))
                print(f"✓ LLM: {cfg.get('model','')}")

        print(f"✓ GWS: {args.gws_data} | 记忆: {gws_instance.long_term_memory.stats()['total']}条")

        if args.auto_tick > 0:
            t = threading.Thread(target=auto_tick_loop, args=(args.auto_tick,), daemon=True)
            t.start()
            print(f"✓ Auto-tick: {args.auto_tick}s")

    server = HTTPServer((args.host, args.port), GWSHandler)
    print(f"✓ http://{args.host}:{args.port}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        if gws_instance:
            gws_instance.save_state()


if __name__ == '__main__':
    main()
