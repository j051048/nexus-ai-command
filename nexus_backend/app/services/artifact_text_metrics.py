"""Consistent body counts: letters/numbers, excluding headings and references."""

import re

_CITATION = re.compile(r"\[(?:EVID:[^\]]+|来源\s*\d+)\]")
_APPENDIX = {"人工复核清单", "资料来源", "参考资料", "参考文献", "目录"}


def body_character_count(markdown: str) -> int:
    lines = []
    appendix = False
    for line in str(markdown or "").splitlines():
        value = line.strip()
        heading = re.match(r"^#{1,6}\s+(.+)", value)
        if heading:
            appendix = heading.group(1).strip() in _APPENDIX
            continue
        if appendix or value.startswith((">", "依据：", "```")):
            continue
        value = re.sub(r"^\s*(?:[-*+]\s+|\d+[.)]\s+)", "", value)
        lines.append(_CITATION.sub("", value))
    return sum(char.isalnum() for char in "".join(lines))
