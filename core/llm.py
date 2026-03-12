"""
LLM 客户端 — GWS 的外部智能接口

两个用途：
1. 情绪提取：文本 → PAD 向量（替换规则词典）
2. 语言层：意识层内容 → 自然语言表达

支持 OpenRouter / SiliconFlow / 任何 OpenAI 兼容 API
"""

import json
import os
from dataclasses import dataclass
from typing import Optional

try:
    import requests
except ImportError:
    requests = None


# === API 提供商配置 ===

PROVIDERS = {
    "openrouter": {
        "base_url": "https://openrouter.ai/api/v1",
        "env_key": "OPENROUTER_API_KEY",
    },
    "siliconflow": {
        "base_url": "https://api.siliconflow.cn/v1",
        "env_key": "SILICONFLOW_API_KEY",
    },
}


@dataclass
class LLMConfig:
    provider: str = "openrouter"
    api_key: str = ""
    model: str = ""           # 留空则用默认
    temperature: float = 0.7
    max_tokens: int = 500

    @property
    def base_url(self) -> str:
        return PROVIDERS[self.provider]["base_url"]

    @property
    def default_model(self) -> str:
        if self.provider == "openrouter":
            return "google/gemini-2.0-flash-001"  # 便宜快速
        elif self.provider == "siliconflow":
            return "Qwen/Qwen2.5-7B-Instruct"
        return "gpt-4o-mini"


class LLMClient:
    """
    统一的 LLM 调用客户端

    用法：
        client = LLMClient(LLMConfig(provider="openrouter", api_key="..."))
        result = client.chat("你好")
    """

    def __init__(self, config: LLMConfig = None):
        self.config = config or self._load_config()

    def _load_config(self) -> LLMConfig:
        """从环境变量或配置文件加载"""
        # 按优先级尝试
        for provider_name, provider_info in PROVIDERS.items():
            api_key = os.environ.get(provider_info["env_key"], "")
            if api_key:
                return LLMConfig(provider=provider_name, api_key=api_key)

        # 从 GWS 配置文件读取
        config_path = os.path.join(os.path.dirname(__file__), "..", "config", "llm.json")
        if os.path.exists(config_path):
            with open(config_path) as f:
                data = json.load(f)
                return LLMConfig(**data)

        return LLMConfig()  # 空配置，调用时会报错

    def chat(
        self,
        messages: list[dict],
        system_prompt: str = "",
        temperature: float = None,
        max_tokens: int = None,
    ) -> str:
        """
        发送聊天请求，返回文本

        messages: [{"role": "user", "content": "..."}]
        """
        if not self.config.api_key:
            return "[LLM 未配置: 缺少 API key]"

        if requests is None:
            return "[LLM 未配置: 需要 requests 库]"

        all_messages = []
        if system_prompt:
            all_messages.append({"role": "system", "content": system_prompt})
        all_messages.extend(messages)

        model = self.config.model or self.config.default_model
        temperature = temperature if temperature is not None else self.config.temperature
        max_tokens = max_tokens or self.config.max_tokens

        try:
            response = requests.post(
                f"{self.config.base_url}/chat/completions",
                headers={
                    "Authorization": f"Bearer {self.config.api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": model,
                    "messages": all_messages,
                    "temperature": temperature,
                    "max_tokens": max_tokens,
                },
                timeout=30,
            )
            response.raise_for_status()
            data = response.json()
            return data["choices"][0]["message"]["content"]
        except Exception as e:
            return f"[LLM 错误: {e}]"

    def chat_json(
        self,
        messages: list[dict],
        system_prompt: str = "",
        temperature: float = 0.3,
    ) -> dict:
        """
        请求 JSON 格式的回复

        自动在 prompt 末尾加 "Reply in JSON format"
        """
        messages = list(messages)  # copy
        if messages:
            messages[-1] = {
                "role": messages[-1]["role"],
                "content": messages[-1]["content"] + "\n\nReply ONLY with valid JSON, no other text.",
            }

        raw = self.chat(messages, system_prompt=system_prompt, temperature=temperature)

        # 尝试解析 JSON
        try:
            # 处理 markdown code block
            text = raw.strip()
            if text.startswith("```"):
                text = text.split("\n", 1)[1]
                if text.endswith("```"):
                    text = text[:-3]
            return json.loads(text.strip())
        except json.JSONDecodeError:
            return {"error": "JSON parse failed", "raw": raw}
