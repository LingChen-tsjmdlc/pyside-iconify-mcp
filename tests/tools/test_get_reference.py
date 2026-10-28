"""get_reference：说明文字与主库签名保持一致，示例代码本身通过 check_code。"""

from __future__ import annotations

import re

import pytest

from pyside_iconify_mcp.common import library
from pyside_iconify_mcp.common.errors import InputError
from pyside_iconify_mcp.tools import check_code, get_reference


def _all_signatures() -> list[library.Signature]:
    sigs = library.load_signatures()
    return [sigs.widget_init, *sigs.functions.values()]


def test_every_parameter_has_a_description() -> None:
    """主库每个参数在说明表里都有英文说明；主库新增参数时这里会失败，提醒补文档。"""
    undocumented = {
        param.name
        for sig in _all_signatures()
        for param in sig.params
        if param.name not in get_reference.PARAM_DOCS
    }
    assert not undocumented


def test_no_description_for_a_parameter_that_does_not_exist() -> None:
    """说明表里没有主库已经删除的参数。"""
    existing = {param.name for sig in _all_signatures() for param in sig.params}
    assert not set(get_reference.PARAM_DOCS) - existing


def test_every_method_has_a_description_and_none_is_stale() -> None:
    """IconWidget 的每个公开方法都有说明，且没有多余的说明。"""
    methods = {method.name for method in library.load_signatures().widget_methods}
    assert methods == set(get_reference.METHOD_DOCS)


def test_topics_are_listed_and_render() -> None:
    """目录列出全部主题，每个主题都能渲染出非空文本并带有标题。"""
    index = get_reference.run()
    for key in get_reference.TOPIC_KEYS:
        assert f"`{key}`" in index
        text = get_reference.run(key)
        assert text.startswith("# ")
        assert len(text) > 200


def test_unknown_topic_is_rejected() -> None:
    """不存在的主题报错，并列出可选主题。"""
    with pytest.raises(InputError, match="overview"):
        get_reference.run("nope")


def test_reference_mentions_library_version() -> None:
    """目录与总览写明对应的主库版本。"""
    assert library.LIB_VERSION in get_reference.run()
    assert library.LIB_VERSION in get_reference.run("overview")


def test_signature_blocks_show_real_defaults() -> None:
    """签名块来自主库存根：能看到真实的默认值和仅限关键字的分隔。"""
    text = get_reference.run("icon_widget")
    assert "autoplay: bool = True," in text
    assert "    *,\n" in text
    assert "setColorLightTheme" in text and "setLightColor" in text  # 后者出现在“不存在”的说明里


def _python_blocks(text: str) -> list[str]:
    return re.findall(r"```python\n(.*?)```", text, re.S)


@pytest.mark.parametrize("key", get_reference.TOPIC_KEYS)
def test_examples_pass_check_code(key: str) -> None:
    """文档里的每段示例代码，用我们自己的检查器检查都没有错误和警告。"""
    for index, block in enumerate(_python_blocks(get_reference.run(key))):
        result = check_code.run(block, verify_icon_names=False)
        assert result["issues"] == [], f"{key} example {index}: {result['issues']}"


def test_there_are_examples() -> None:
    """主要主题都带有示例。"""
    for key in ("overview", "icon_widget", "get_icon", "set_icon", "colors", "sizes", "animation"):
        assert _python_blocks(get_reference.run(key)), key


def test_pitfall_rows_have_three_columns() -> None:
    """错误对照表每行都是三列。"""
    for wrong, right, why in get_reference._PITFALLS:
        assert wrong and right and why
        assert "|" not in wrong + right + why
