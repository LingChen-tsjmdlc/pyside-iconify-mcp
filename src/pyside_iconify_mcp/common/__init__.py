"""多个工具共用的代码，以及对外部世界的封装。

| 文件               | 内容                                              |
| ------------------ | ------------------------------------------------- |
| errors.py          | 工具入参错误 InputError                           |
| library.py         | 对主库 pyside-iconify 的全部依赖，只有它导入主库    |
| iconify_api.py     | Iconify 公共 API 客户端（urllib + 内存缓存）       |
| lookup.py          | 批量核对图标名并找相近图标（check_icons、check_code 共用） |
| colors.py          | CSS / SVG 标准颜色名表                            |
| tool_annotations.py | 工具的只读标注（离线 / 联网两种）                |

放进来的标准：至少两个工具要用；或者它是对外部世界（主库、Iconify、标准）的封装与数据。
只有一个工具用的代码留在那个工具自己的文件里，不要往这里放。
"""
