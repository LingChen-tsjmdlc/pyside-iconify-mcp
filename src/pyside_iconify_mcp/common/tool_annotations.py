"""所有工具共用的 MCP 工具标注：工具都是只读、可重复调用的，区别只在是否联网。"""

OFFLINE_READ: dict[str, bool] = {
    "read_only_hint": True,
    "idempotent_hint": True,
    "open_world_hint": False,
}
ONLINE_READ: dict[str, bool] = {
    "read_only_hint": True,
    "idempotent_hint": True,
    "open_world_hint": True,
}
