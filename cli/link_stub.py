#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""软链残骸识别 —— 导入通道与「技能资产补齐」工具共用的判据。

抽成独立模块的原因：同一套判据要在两处使用，绝不能各写一份。
`cli/import-clawhub.py`（入库时拦截）与 `cli/fetch-skill-assets.py`（事后检测
存量残骸）一旦判据漂移，就会出现「导入时放行、补齐时删除」这类自相矛盾的行为。

## 两种形态都要拦，缺一不可

1. `symlink`——打包器保留了链接类型。zip 走 external_attr 高 16 位的 S_IFLNK
   （GitHub 的 archive zip 实测为 0o120777），tar 走 `issym()`。
2. `flattened`——打包器把链接当普通文件写，落盘内容就是**链接目标路径文本**。
   ClawHub 原生包的 zip 条目不带宽带 external_attr（实测 0），只有内容可判，
   因此光靠标记会漏掉本库实际踩到的那个案例。

不拦的后果不是「多两个没用的文件」：悬空文本会被当正常资产落盘，而正文里对
目标的引用全部失效（ui-ux-pro-max 的 `scripts/search.py` 就是这样悬空的，
12 处调用指向一个从未存在过的文件）。
"""

from __future__ import annotations

import re

# `../`、`./` 开头、只含路径字符、可选结尾斜杠，且**整串就是内容的全部**。
_RELPATH_STUB_RE = re.compile(r"^(?:\.{1,2}/)+[\w.\-/]+/?$")

# 超过这个长度就不再像「被拍平的链接目标」了（目标路径再深也到不了 256 字节）。
STUB_MAX_BYTES = 256


def safe_relpath(name: str) -> str:
    """规范化相对路径，拒绝绝对路径与目录穿越。"""
    name = name.replace("\\", "/").lstrip("/")
    if not name or ".." in name.split("/"):
        return ""
    return name


def is_link_stub(data: bytes) -> bool:
    """内容是否为「一段孤立的相对路径」——软链被拍平后的典型形态。

    判据要紧的一点：真实残骸**不含任何换行**。本库实测 `scripts` 为 34 字节，
    恰好等于 `../../../src/ui-ux-pro-max/scripts` 的长度；GitHub zip 里的
    `gallery/data/styles.csv` 为 39 字节，同样与目标路径等长。带上换行的
    「一行路径文本」更像人写的说明文件，不该误伤。
    """
    if not data or len(data) > STUB_MAX_BYTES:
        return False
    if b"\n" in data or b"\r" in data:
        return False
    try:
        text = data.decode("utf-8").strip()
    except UnicodeDecodeError:
        return False
    return bool(_RELPATH_STUB_RE.match(text))


def classify_link_entry(rel: str, data: bytes, symlink_mode: bool) -> tuple[str, str] | None:
    """判定条目是否为软链残骸，返回 (kind, detail)，否则 None。"""
    if symlink_mode:
        return ("symlink", data.decode("utf-8", "ignore").strip() or "<目录链接>")
    if is_link_stub(data):
        return ("flattened", data.decode("utf-8", "ignore").strip())
    return None


def zip_symlink_mode(info) -> bool:
    """zip 条目是否带 S_IFLNK 标记（mode 高 16 位）。"""
    return ((info.external_attr >> 16) & 0xF000) == 0xA000


def scan_dir_for_stubs(root, max_bytes: int = 64 * 1024) -> list[tuple[str, str]]:
    """扫描一个**已落盘**目录，返回疑似残骸的 `(相对路径, 链接目标)`。

    用于清理存量：导入器只在入库那一刻拦截，历史上已经落盘的残骸得靠这里发现。
    只读小于 `max_bytes` 的文件——残骸永远是几十字节，不必读大文件。
    """
    from pathlib import Path

    out: list[tuple[str, str]] = []
    base = Path(root)
    for p in sorted(base.rglob("*")):
        if not p.is_file():
            continue
        try:
            if p.stat().st_size > max_bytes:
                continue
            data = p.read_bytes()
        except OSError:
            continue
        if is_link_stub(data):
            out.append((str(p.relative_to(base)).replace("\\", "/"),
                        data.decode("utf-8", "ignore").strip()))
    return out
