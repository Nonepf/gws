#!/usr/bin/env python3
"""
GWS Web Dashboard 服务器

用法:
    python3 dashboard.py                    # 默认端口 8080
    python3 dashboard.py --port 9000        # 指定端口
    python3 dashboard.py --with-gws         # 同时启动 GWS 实例
    python3 dashboard.py --gws-data ./data  # 指定 GWS 数据目录

功能:
    - GET /              → Dashboard HTML
    - GET /api/status    → GWS 系统状态 JSON
    - POST /api/input    → 发送输入到 GWS
    - POST /api/tick     → 手动触发自主探索

注意: 这是一个开发工具，不要在公网暴露。
"""

import argparse
import json
import sys
import threading
import time
from http.server import HTTPServer, SimpleHTTPRequestHandler
from pathlib import Path
from urllib.parse import urlparse, parse_qs

# GWS 实例（可选）
gws_instance = None
gws_lock = threading.Lock()


class GWSHandler(SimpleHTTPRequestHandler):
    """处理 HTTP 请求"""

    def do_GET(self):
        parsed = urlparse(self.path)
        
        if parsed.path == '/' or parsed.path == '/index.html':
            self._serve_file('web/dashboard.html', 'text/html')
        elif parsed.path == '/api/status':
            self._api_status()
        else:
            self.send_error(404)

    def do_POST(self):
        parsed = urlparse(self.path)
        
        if parsed.path == '/api/input':
            self._api_input()
        elif parsed.path == '/api/tick':
            self._api_tick()
        else:
            self.send_error(404)

    def _serve_file(self, rel_path, content_type):
        """服务静态文件"""
        base = Path(__file__).parent
        file_path = base / rel_path
        if file_path.exists():
            self.send_response(200)
            self.send_header('Content-Type', f'{content_type}; charset=utf-8')
            self.end_headers()
            self.wfile.write(file_path.read_bytes())
        else:
            self.send_error(404)

    def _api_status(self):
        """返回 GWS 状态"""
        with gws_lock:
            if gws_instance:
                status = gws_instance.get_status()
            else:
                status = {"error": "GWS not initialized", "demo": True}
        
        self._json_response(status)

    def _api_input(self):
        """接收用户输入"""
        content_len = int(self.headers.get('Content-Length', 0))
        body = self.rfile.read(content_len)
        
        try:
            data = json.loads(body)
            text = data.get('text', '')
        except json.JSONDecodeError:
            self._json_response({"error": "Invalid JSON"}, 400)
            return

        with gws_lock:
            if gws_instance:
                result = gws_instance.on_input(text)
                gws_instance.save_state()
                self._json_response(result)
            else:
                self._json_response({"error": "GWS not initialized"}, 503)

    def _api_tick(self):
        """手动触发自主探索"""
        with gws_lock:
            if gws_instance:
                result = gws_instance.autonomous_tick()
                gws_instance.save_state()
                self._json_response(result)
            else:
                self._json_response({"error": "GWS not initialized"}, 503)

    def _json_response(self, data, status=200):
        """发送 JSON 响应"""
        body = json.dumps(data, ensure_ascii=False, default=str).encode()
        self.send_response(status)
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Content-Length', len(body))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format, *args):
        """简化日志"""
        print(f"[{time.strftime('%H:%M:%S')}] {args[0]}")


def auto_tick_loop(interval=30):
    """后台自动 tick 线程"""
    while True:
        time.sleep(interval)
        with gws_lock:
            if gws_instance:
                try:
                    gws_instance.autonomous_tick()
                    gws_instance.save_state()
                except Exception as e:
                    print(f"[auto-tick] Error: {e}")


def main():
    global gws_instance
    
    parser = argparse.ArgumentParser(description='GWS Web Dashboard')
    parser.add_argument('--port', type=int, default=8080)
    parser.add_argument('--host', default='127.0.0.1')
    parser.add_argument('--with-gws', action='store_true', help='启动内置 GWS 实例')
    parser.add_argument('--gws-data', default='./data', help='GWS 数据目录')
    parser.add_argument('--llm', action='store_true', help='启用 LLM（需要 config/llm.json）')
    parser.add_argument('--auto-tick', type=int, default=0, help='自动探索间隔（秒，0=关闭）')
    args = parser.parse_args()

    # 初始化 GWS
    if args.with_gws:
        sys.path.insert(0, str(Path(__file__).parent))
        from core.gws import GWS
        
        gws_instance = GWS(workspace_dir=args.gws_data)
        gws_instance.start()
        
        if args.llm:
            config_path = Path(__file__).parent / 'config' / 'llm.json'
            if config_path.exists():
                cfg = json.loads(config_path.read_text())
                gws_instance.enable_llm(
                    provider=cfg.get('provider', 'openrouter'),
                    api_key=cfg.get('api_key', ''),
                    model=cfg.get('model', ''),
                )
                print("✓ LLM 已启用")
            else:
                print("⚠ 未找到 config/llm.json，使用离线模式")
        
        print(f"✓ GWS 已启动 (数据: {args.gws_data})")
        
        # 自动探索线程
        if args.auto_tick > 0:
            t = threading.Thread(target=auto_tick_loop, args=(args.auto_tick,), daemon=True)
            t.start()
            print(f"✓ 自动探索已启动 (间隔: {args.auto_tick}秒)")

    # 启动服务器
    server = HTTPServer((args.host, args.port), GWSHandler)
    print(f"✓ Dashboard: http://{args.host}:{args.port}")
    print("  按 Ctrl+C 停止")
    
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n停止...")
        if gws_instance:
            gws_instance.save_state()
            print("✓ 状态已保存")


if __name__ == '__main__':
    main()
