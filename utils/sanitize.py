"""Filename sanitization and timestamp extraction.

Provides utilities for cleaning filenames and folder names by removing
illegal characters (both ASCII and Chinese punctuation), extracting
timestamps from ZIP filenames, and generating standardized document names.
"""

import re
from datetime import datetime
from pathlib import Path
from typing import Optional

# 匹配文件名中的非法字符：ASCII 特殊字符 + 中文标点符号
# 包括：<>:"/\|?* 以及 【】（）《》""''：；，。！？ 和方括号
ILLEGAL_CHARS: str = r'[<>:"/\\|?*【】（）《》""''：；，。！？\[\]]'


def clean_filename(name: str, max_length: int = 200) -> str:
    """Clean a filename by removing illegal characters and truncating if needed.

    Replaces illegal characters with underscores, collapses consecutive
    underscores/spaces/dots into a single underscore, and truncates the
    stem to fit within ``max_length`` while preserving the file extension.

    清理文件名时保留扩展名不变，仅对主文件名部分进行清洗和截断。
    若清洗后主文件名为空，则使用 "unnamed" 作为默认值。

    Args:
        name: The original filename (may contain illegal characters).
        max_length: Maximum total length of the cleaned filename
            (stem + extension). Defaults to 200.

    Returns:
        A cleaned filename with illegal characters replaced and length
        constrained. Extension is always preserved.

    Raises:
        ValueError: If ``name`` is empty.

    Examples:
        >>> clean_filename("report【test】.pdf")
        'report_test.pdf'
        >>> clean_filename("test___report")
        'test_report'
    """
    if not name:
        raise ValueError("name must not be empty")

    path = Path(name)
    stem = path.stem
    ext = path.suffix

    # 替换所有非法字符为下划线
    stem = re.sub(ILLEGAL_CHARS, "_", stem)
    # 合并连续的下划线、空格、点号为单个下划线
    stem = re.sub(r"[_\s.]+", "_", stem)
    # 去除首尾的下划线、点号、空格
    stem = stem.strip("_. ")

    # 清洗后若主文件名为空，使用默认名称
    if not stem:
        stem = "unnamed"

    # 按 max_length 截断，确保 stem + ext 不超过限制
    max_stem = max_length - len(ext)
    if len(stem) > max_stem:
        stem = stem[:max_stem]

    return stem + ext


def clean_foldername(name: str) -> str:
    """Clean a folder name with stricter rules than filename cleaning.

    Removes illegal characters, then keeps only word characters (letters,
    digits, underscores) and Chinese Unicode range (\\u4e00-\\u9fff),
    collapsing all other sequences into single underscores.

    文件夹名清洗比文件名更严格：仅保留字母数字、下划线和中文字符，
    其余所有字符序列统一替换为单个下划线。

    Args:
        name: The original folder name.

    Returns:
        A cleaned folder name containing only safe characters.
        Returns "unnamed" if the result would be empty.

    Examples:
        >>> clean_foldername("test【report】（2025）")
        'test_report_2025'
    """
    # 先替换已知的非法中文/ASCII 标点
    name = re.sub(ILLEGAL_CHARS, "_", name)
    # 仅保留单词字符和中文字符，其余全部替换为下划线
    name = re.sub(r"[^\w\u4e00-\u9fff]+", "_", name)
    # 合并连续下划线
    name = re.sub(r"_+", "_", name)
    # 去除首尾下划线和空格
    name = name.strip("_ ")
    return name or "unnamed"


def extract_timestamp_from_zip(filename: str) -> str:
    """Extract an 8-digit date (YYYYMMDD) from a ZIP filename.

    Tries four patterns in order of specificity:
    1. ``^(\d{8})`` — 8 digits at the start (e.g., ``20251202...``)
    2. ``(\d{8})_`` — 8 digits followed by underscore
    3. ``_(\d{8})`` — 8 digits preceded by underscore
    4. ``(\d{14})`` — 14-digit timestamp (YYYYMMDDHHmmss), truncated to 8

    按优先级尝试四种模式匹配日期：从最精确的开头8位数字开始，
    逐步放宽到14位时间戳（截取前8位）。每种模式都会验证日期合法性，
    无效日期（如 20251301）会被跳过。

    Args:
        filename: The ZIP filename to extract the date from.

    Returns:
        An 8-digit date string in YYYYMMDD format.
        Returns today's date if no valid timestamp is found.

    Examples:
        >>> extract_timestamp_from_zip("202512021157134086066.zip")
        '20251202'
    """
    patterns: list[str] = [
        r"^(\d{8})",
        r"(\d{8})_",
        r"_(\d{8})",
        r"(\d{14})",
    ]
    for pattern in patterns:
        match = re.search(pattern, filename)
        if match:
            ts = match.group(1)[:8]
            try:
                # 验证日期是否合法（如 20251301 会抛出 ValueError）
                datetime.strptime(ts, "%Y%m%d")
                return ts
            except ValueError:
                continue
    # 所有模式均未匹配或日期无效时，返回当天日期
    return datetime.now().strftime("%Y%m%d")


def generate_doc_filename(
    zip_filename: str,
    report_title: str,
    publish_date: Optional[str] = None,
) -> str:
    """Generate a standardized document filename from a ZIP and title.

    Produces a filename in the format ``YYYYMMDD_sanitized_title.ext``,
    where the date comes from the ZIP filename and the extension defaults
    to ``.pdf`` if the original was ``.zip`` or missing.

    生成的文件名格式为 ``YYYYMMDD_清洗后的标题.扩展名``。
    注意：``publish_date`` 参数当前未被使用（保留以兼容未来按发布日期命名的需求），
    日期始终从 ``zip_filename`` 中提取。

    Args:
        zip_filename: The original ZIP filename (used for date and extension).
        report_title: The report title to include in the filename.
        publish_date: **Unused.** Reserved for future date-based naming.

    Returns:
        A standardized filename like ``20251202_测试报告.pdf``.

    Examples:
        >>> generate_doc_filename("202512021157134086066.zip", "测试报告")
        '20251202_测试报告.pdf'
    """
    ts = extract_timestamp_from_zip(zip_filename)
    ext = Path(zip_filename).suffix
    # ZIP 文件的扩展名不保留 —— 内部文档的扩展名由实际文件决定
    if ext.lower() == ".zip":
        ext = ""
    if not ext:
        ext = ".pdf"  # 默认使用 PDF 扩展名

    clean_title = clean_filename(report_title)
    # 移除标题中的点号和空格，避免文件名混乱
    clean_title = clean_title.replace(".", "_").replace(" ", "")
    clean_title = clean_title.strip()

    return f"{ts}_{clean_title}{ext}"
