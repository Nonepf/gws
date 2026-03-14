#!/usr/bin/env python3
"""
AWARE Dashboard — WebSocket 实时流服务器

特性：
- WebSocket 推送实时数据（情绪曲线、驱动力、黑板流）
- HTTP API 用于一次性查询
- 自动心跳和重连
- 轻量级（仅依赖 websockets + 标准库）

Usage:
    python3 dashboard_server.py --port 8080 --with-aware --aware-data ./data
"""

import argparse
import asyncio
import json
import sys
import time
import uuid
import threading
from datetime import datetime
from pathlib import Path
from http.server import HTTPServer, SimpleHTTPRequestHandler

# WebSocket 支持（轻量实现）
try:
    import websockets
    ws_serve = websockets.serve
    HAS_WEBSOCKETS = True
except ImportError:
    HAS_WEBSOCKETS = False

# AWARE 实例
aware_instance = None
chat_history = []
chat_history_file = None

# WebSocket 客户端管理
ws_clients: set = set()
ws_lock = threading.Lock()
_main_loop = None  # 主事件循环引用

# 异步任务
tasks = {}
tasks_lock = threading.Lock()


class DashboardHTTPHandler(SimpleHTTPRequestHandler):
    """HTTP 处理器 — API + 静态文件"""
    
    def do_GET(self):
        path = self.path.split('?')[0]
        routes = {
            '/': self._serve_index,
            '/api/status': self._api_status,
            '/api/dashboard': self._api_dashboard,
            '/api/history': self._api_history,
            '/api/events': self._api_events,
            '/api/task': self._api_task,
            '/api/drives/history': self._api_drives_history,
            '/api/emotion/timeseries': self._api_emotion_timeseries,
        }
        handler = routes.get(path)
        if handler:
            handler()
        else:
            # 静态文件
            self.send_error(404)
    
    def do_POST(self):
        routes = {
            '/api/input': self._api_input,
            '/api/tick': self._api_tick,
            '/api/trigger': self._api_trigger,
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
        if aware_instance:
            self._json(aware_instance.get_status())
        else:
            self._json({"error": "not initialized"})
    
    def _api_dashboard(self):
        """完整 Dashboard 数据"""
        if aware_instance:
            self._json(aware_instance.get_dashboard_data())
        else:
            self._json({"error": "not initialized"})
    
    def _api_history(self):
        self._json({"history": chat_history[-50:]})
    
    def _api_events(self):
        """获取最近事件"""
        if aware_instance:
            events = aware_instance.event_bus.get_history(limit=50)
            self._json({"events": [e.to_dict() for e in events]})
        else:
            self._json({"events": []})
    
    def _api_drives_history(self):
        """驱动力历史"""
        if aware_instance:
            self._json({"history": aware_instance.drives.get_history()})
        else:
            self._json({"history": []})
    
    def _api_emotion_timeseries(self):
        """情绪时间序列"""
        if aware_instance:
            self._json({"series": aware_instance.emotion_engine.get_time_series()})
        else:
            self._json({"series": []})
    
    def _api_task(self):
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
        """异步处理用户输入"""
        try:
            data = self._read_body()
            text = data.get('text', '')
        except:
            self._json({"error": "Invalid JSON"}, 400)
            return
        
        if not aware_instance:
            self._json({"error": "AWARE not initialized"}, 503)
            return
        
        task_id = str(uuid.uuid4())[:8]
        with tasks_lock:
            tasks[task_id] = {"status": "processing", "text": text}
        
        self._json({"task_id": task_id, "status": "processing"})
        
        t = threading.Thread(target=_process_input, args=(task_id, text), daemon=True)
        t.start()
    
    def _api_tick(self):
        if not aware_instance:
            self._json({"error": "AWARE not initialized"}, 503)
            return
        result = aware_instance.tick()
        aware_instance.save_state()
        
        # 广播到 WebSocket
        _broadcast_ws({"type": "tick", "data": result})
        
        self._json(result)
    
    def _api_trigger(self):
        """手动触发某个子系统"""
        try:
            data = self._read_body()
            action = data.get('action', '')
        except:
            self._json({"error": "Invalid JSON"}, 400)
            return
        
        if not aware_instance:
            self._json({"error": "AWARE not initialized"}, 503)
            return
        
        result = {}
        if action == "proactive_speech":
            trigger = aware_instance.check_proactive_speech()
            result = {"triggered": trigger is not None, "data": trigger}
        elif action == "tick":
            result = aware_instance.tick()
        elif action == "save":
            result = aware_instance.save_state()
        
        self._json(result)
    
    def log_message(self, format, *args):
        pass


def _process_input(task_id: str, text: str):
    """后台处理用户输入"""
    global chat_history

    try:
        # 1. 处理输入
        input_result = aware_instance.on_input(text)

        # 2. 推进系统
        tick_result = aware_instance.tick()

        # 3. 广播状态
        _broadcast_ws({"type": "input_received", "data": {
            "text": text,
            "emotion": input_result.get("emotion_label", ""),
        }})

        # 4. 获取意识层和黑板
        conscious = aware_instance.get_output() or []
        bb_context = [e.to_dict() for e in aware_instance.blackboard.get_recent(seconds=300)]

        # 5. LLM 回复
        response_text = None
        if aware_instance.language_layer:
            try:
                conscious_ctx = aware_instance.workspace.get_consciousness()
                influence = aware_instance.emotion_engine.get_influence()
                memories = aware_instance.long_term_memory.retrieve(
                    query=text, emotion_bias=aware_instance.emotion_engine.state, limit=3,
                )
                memory_context = [m.content for m in memories]
                response_text = aware_instance.language_layer.respond_to_user(
                    user_message=text,
                    conscious_outputs=conscious_ctx,
                    emotion_influence=influence,
                    memory_context=memory_context,
                    blackboard_context=bb_context,
                )
                aware_instance.urge.on_speech_delivered()
                aware_instance.drives.on_expression_delivered()
            except Exception as e:
                response_text = f"[回复失败: {e}]"

        aware_instance.save_state()

        # 6. 聊天历史
        chat_history.append({"role": "user", "text": text, "time": time.time()})
        if response_text:
            chat_history.append({"role": "aware", "text": response_text, "time": time.time(),
                                "emotion": input_result.get("emotion_label", "")})
        _save_chat()

        # 7. 完成
        with tasks_lock:
            tasks[task_id] = {
                "status": "done",
                "response": response_text,
                "emotion": input_result.get("emotion_label", ""),
                "consciousness": [c.get("content", "")[:200] for c in conscious],
                "has_llm": aware_instance.language_layer is not None,
                "dashboard": aware_instance.get_dashboard_data(),
            }

        _broadcast_ws({"type": "response", "data": {
            "task_id": task_id,
            "response": response_text,
            "emotion": input_result.get("emotion_label", ""),
        }})

    except Exception as e:
        with tasks_lock:
            tasks[task_id] = {"status": "error", "error": str(e)}
        _broadcast_ws({"type": "error", "data": {"error": str(e)}})


# === WebSocket ===

def _broadcast_ws(message: dict):
    """广播消息到所有 WebSocket 客户端"""
    global ws_clients
    if not HAS_WEBSOCKETS:
        return
    if _main_loop is None or _main_loop.is_closed():
        return
    data = json.dumps(message, ensure_ascii=False, default=str)
    with ws_lock:
        if not ws_clients:
            return
        dead = set()
        for ws in list(ws_clients):
            try:
                asyncio.run_coroutine_threadsafe(ws.send(data), _main_loop)
            except Exception:
                dead.add(ws)
        ws_clients -= dead


async def _ws_handler(websocket):
    """WebSocket 连接处理"""
    with ws_lock:
        ws_clients.add(websocket)
    
    try:
        # 发送初始状态
        if aware_instance:
            await websocket.send(json.dumps({
                "type": "init",
                "data": aware_instance.get_dashboard_data(),
            }, ensure_ascii=False, default=str))
        
        # 保持连接
        async for message in websocket:
            # 客户端消息处理
            try:
                data = json.loads(message)
                if data.get("type") == "ping":
                    await websocket.send(json.dumps({"type": "pong"}))
            except:
                pass
    except:
        pass
    finally:
        with ws_lock:
            ws_clients.discard(websocket)


async def _ws_broadcast_loop():
    """定期广播状态更新"""
    while True:
        await asyncio.sleep(3)
        if aware_instance and ws_clients:
            try:
                data = {
                    "type": "update",
                    "data": {
                        "emotion": aware_instance.emotion_engine.get_influence(),
                        "drives": aware_instance.drives.status(),
                        "urge": aware_instance.urge.status(),
                        "blackboard": {
                            "status": aware_instance.blackboard.status(),
                            "recent": [e.to_dict() for e in aware_instance.blackboard.get_recent(seconds=600)],
                        },
                        "intentions": aware_instance.intentions.get_intention_radar(),
                        "emotion_series": aware_instance.emotion_engine.get_time_series(limit=30),
                        "drives_history": aware_instance.drives.get_history(limit=30),
                        "events": {
                            "recent": [e.to_dict() for e in aware_instance.event_bus.get_history(limit=30)],
                        },
                        "subconscious": aware_instance.subconscious.status(),
                    },
                }
                _broadcast_ws(data)
            except Exception as e:
                print(f"[WS] Broadcast error: {e}", flush=True)


# === Helpers ===

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


def _run_http_server(host: str, port: int):
    """在单独线程运行 HTTP 服务器"""
    server = HTTPServer((host, port), DashboardHTTPHandler)
    print(f"✓ HTTP: http://{host}:{port}", flush=True)
    server.serve_forever()


def main():
    global aware_instance, chat_history_file
    
    parser = argparse.ArgumentParser(description="AWARE Dashboard Server")
    parser.add_argument('--port', type=int, default=8080)
    parser.add_argument('--ws-port', type=int, default=8081)
    parser.add_argument('--host', default='127.0.0.1')
    parser.add_argument('--with-aware', action='store_true')
    parser.add_argument('--aware-data', default='./data')
    parser.add_argument('--llm', action='store_true')
    args = parser.parse_args()
    
    if args.with_aware:
        sys.path.insert(0, str(Path(__file__).parent))
        from core.gws import AWARE
        
        aware_instance = AWARE(workspace_dir=args.aware_data)
        aware_instance.start()
        chat_history_file = aware_instance.workspace_dir / "chat_history.json"
        _load_chat()
        
        if args.llm:
            cfg_path = Path(__file__).parent / 'config' / 'llm.json'
            if cfg_path.exists():
                cfg = json.loads(cfg_path.read_text())
                aware_instance.enable_llm(
                    provider=cfg.get('provider', ''),
                    api_key=cfg.get('api_key', ''),
                    model=cfg.get('model', ''),
                )
                print(f"✓ LLM: {cfg.get('model', '')}")
        
        print(f"✓ AWARE: {args.aware_data} | 记忆: {aware_instance.long_term_memory.stats()['total']}条")
    
    # HTTP 服务器（线程）
    http_thread = threading.Thread(
        target=_run_http_server,
        args=(args.host, args.port),
        daemon=True,
    )
    http_thread.start()
    
    # WebSocket 服务器
    if HAS_WEBSOCKETS:
        async def ws_main():
            global _main_loop
            _main_loop = asyncio.get_event_loop()
            async with ws_serve(_ws_handler, args.host, args.ws_port):
                print(f"✓ WebSocket: ws://{args.host}:{args.ws_port}", flush=True)
                asyncio.create_task(_ws_broadcast_loop())
                await asyncio.Future()
        
        try:
            asyncio.run(ws_main())
        except KeyboardInterrupt:
            print("\n关闭...")
            if aware_instance:
                aware_instance.save_state()
    else:
        print("⚠ websockets 未安装，仅 HTTP 模式 (pip install websockets)")
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            print("\n关闭...")
            if aware_instance:
                aware_instance.save_state()


if __name__ == '__main__':
    main()
