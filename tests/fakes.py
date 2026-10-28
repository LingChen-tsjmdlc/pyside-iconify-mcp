"""测试用的假 Iconify API：不联网，数据格式与真实接口一致。"""

from __future__ import annotations

import urllib.parse

from pyside_iconify_mcp.common.iconify_api import ApiError

_ANIMATED_BODY = (
    '<path fill="none" stroke="currentColor" stroke-linecap="round" stroke-width="2" '
    'd="M12 3c4.97 0 9 4.03 9 9"><animateTransform attributeName="transform" dur="1.5s" '
    'repeatCount="indefinite" type="rotate" values="0 12 12;360 12 12"/></path>'
)

COLLECTIONS: dict[str, dict[str, object]] = {
    "mdi": {
        "prefix": "mdi",
        "width": 24,
        "height": 24,
        "icons": {
            "home": {"body": '<path fill="currentColor" d="M0 0h1v1z"/>'},
            "home-outline": {"body": '<path fill="currentColor" d="M0 0h2v2z"/>'},
            "cog": {"body": '<path fill="currentColor" d="M0 0h3v3z"/>'},
        },
        "aliases": {"gear": {"parent": "cog"}},
    },
    "logos": {
        "prefix": "logos",
        "width": 256,
        "height": 256,
        "icons": {
            "google-icon": {
                "body": '<path fill="#4285f4" d="M0 0h1v1z"/><path fill="#ea4335" d="M1 1h1v1z"/>'
            },
            "mixed": {
                "body": '<path fill="#4285f4" d="M0 0h1v1z"/><path fill="currentColor" d="M1 1h1v1z"/>'
            },
        },
    },
    "line-md": {
        "prefix": "line-md",
        "width": 24,
        "height": 24,
        "icons": {"loading-loop": {"body": _ANIMATED_BODY}},
    },
    "evil": {
        "prefix": "evil",
        "icons": {
            "fine": {"body": '<path fill="currentColor" d="M0 0h1v1z"/>'},
            "script": {"body": "<script>alert(1)</script>"},
        },
    },
}

# 关键词 -> 命中的图标（搜索假实现用：所有词都出现在名字里才算命中）
SEARCHABLE = [
    "mdi:home",
    "mdi:home-outline",
    "mdi:cog",
    "lucide:home",
    "logos:google-icon",
    "line-md:loading-loop",
]


class FakeIconify:
    """假的 Iconify 服务；记录收到的所有地址。"""

    def __init__(self) -> None:
        self.urls: list[str] = []
        self.fail: ApiError | None = None

    def __call__(self, url: str) -> object:
        self.urls.append(url)
        if self.fail is not None:
            raise self.fail
        parsed = urllib.parse.urlparse(url)
        query = urllib.parse.parse_qs(parsed.query)
        if parsed.path == "/search":
            return self._search(query)
        prefix = parsed.path.removesuffix(".json").lstrip("/")
        collection = COLLECTIONS.get(prefix)
        if collection is None:
            return 404
        wanted = query["icons"][0].split(",")
        icons = collection["icons"]
        aliases = collection.get("aliases", {})
        assert isinstance(icons, dict) and isinstance(aliases, dict)
        out_icons: dict[str, object] = {}
        out_aliases: dict[str, object] = {}
        not_found: list[str] = []
        for name in wanted:
            if name in icons:
                out_icons[name] = icons[name]
            elif name in aliases:
                out_aliases[name] = aliases[name]
                out_icons[aliases[name]["parent"]] = icons[aliases[name]["parent"]]
            else:
                not_found.append(name)
        document: dict[str, object] = {
            "prefix": prefix,
            "lastModified": 1,
            "aliases": out_aliases or [],  # 真实接口没有别名时返回空列表
            "icons": out_icons,
        }
        for key in ("width", "height"):
            if key in collection:
                document[key] = collection[key]
        if not_found:
            document["not_found"] = not_found
        return document

    def _search(self, query: dict[str, list[str]]) -> object:
        words = query["query"][0].lower().split()
        prefix = query.get("prefix", [None])[0]
        hits = [
            icon
            for icon in SEARCHABLE
            if all(word in icon.partition(":")[2] for word in words)
            and (prefix is None or icon.startswith(prefix + ":"))
        ]
        used = {icon.partition(":")[0] for icon in hits}
        return {
            "icons": hits,
            "total": len(hits),
            "limit": int(query["limit"][0]),
            "start": 0,
            "collections": {
                p: {
                    "name": p.upper(),
                    "total": 100,
                    "license": {"title": "MIT", "spdx": "MIT"},
                }
                for p in used
            },
        }
