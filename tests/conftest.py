"""测试共用的夹具。"""

from __future__ import annotations

from collections.abc import Iterator

import pytest

from pyside_iconify_mcp.common import iconify_api as api_module
from pyside_iconify_mcp.common.iconify_api import IconifyApi
from tests.fakes import FakeIconify


@pytest.fixture
def fake() -> FakeIconify:
    """假服务实例。"""
    return FakeIconify()


@pytest.fixture
def api(fake: FakeIconify) -> IconifyApi:
    """接到假服务上的客户端。"""
    return IconifyApi(fetch=fake)


@pytest.fixture
def default_api(api: IconifyApi, monkeypatch: pytest.MonkeyPatch) -> Iterator[IconifyApi]:
    """把共享客户端换成假的，供走服务层的测试使用。"""
    monkeypatch.setattr(api_module, "_default_api", api)
    yield api
