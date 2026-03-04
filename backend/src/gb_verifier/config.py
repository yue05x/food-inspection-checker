from __future__ import annotations

import json
import os
from dataclasses import dataclass
from typing import Optional


DEFAULT_CONFIG_PATH = "config.local.json"


@dataclass(frozen=True)
class AppConfig:
    mcp_url: str
    test_txt_path: str


def load_mcp_url(cli_mcp_url: Optional[str], config_path: str) -> Optional[str]:
    """
    Priority: CLI > env var > local config file.
    """
    if cli_mcp_url:
        return cli_mcp_url.strip()

    env = os.environ.get("TAVILY_MCP_URL")
    if env:
        return env.strip()

    if config_path and os.path.exists(config_path):
        try:
            with open(config_path, "r", encoding="utf-8") as f:
                cfg = json.load(f)
            if isinstance(cfg, dict) and isinstance(cfg.get("TAVILY_MCP_URL"), str):
                return cfg["TAVILY_MCP_URL"].strip()
        except Exception:
            return None

    return None


def build_config(cli_mcp_url: Optional[str], config_path: str, test_txt_path: Optional[str]) -> AppConfig:
    mcp_url = load_mcp_url(cli_mcp_url, config_path)
    if not mcp_url:
        raise ValueError("Missing Tavily MCP URL")

    test_txt = test_txt_path or os.environ.get("TEST_TXT", "test.txt")
    return AppConfig(mcp_url=mcp_url, test_txt_path=test_txt)
