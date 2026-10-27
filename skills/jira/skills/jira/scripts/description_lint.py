#!/usr/bin/env python3
# Copyright (c) 2026 SerComm Corporation. All Rights Reserved.
#
# SerComm Corporation reserves the right to make changes to this document
# without notice. SerComm Corporation makes no warranty, representation or
# guarantee regarding the suitability of its products for any particular
# purpose.
#
# SerComm Corporation assumes no liability arising out of the application or
# use of any product or circuit.
#
# SerComm Corporation specifically disclaims any and all liability, including
# without limitation consequential or incidental damages; neither does it convey
# any license under its patent rights, nor the rights of others.

"""Description quality checks for ``--structured`` story creation.

This is the code backstop for the writing rules in SKILL.md: prompts can be
ignored, checks cannot. Section titles are matched in English and Chinese so
existing tickets keep working; vague terms are checked in both languages, but
a line that carries a number is exempt (``P95 < 2s`` is measurable, "fast" is
not).
"""

import re

REQUIRED_SECTIONS = [
    ("Background & Goals", ("background", "goal", "背景", "目标")),
    ("User Story", ("user story", "用户故事")),
    ("Requirements", ("requirement", "需求")),
    (
        "Acceptance Criteria",
        ("acceptance criteria", "acceptance", "验收标准", "验收条件", "验证标准"),
    ),
]

OPTIONAL_SECTIONS = [
    ("Technical Notes", ("technical", "impact", "技术要点", "影响范围", "技术方案")),
    ("Dependencies & Risks", ("dependenc", "risk", "依赖", "风险")),
]

VAGUE_TERMS_ZH = [
    "良好",
    "较好",
    "较高",
    "快速",
    "合理",
    "尽量",
    "尽快",
    "友好",
    "高性能",
    "适当",
    "若干",
    "完善",
    "优化",
    "正常",
]

VAGUE_TERMS_EN = [
    "good",
    "better",
    "fast",
    "quick",
    "stable",
    "friendly",
    "reasonable",
    "appropriate",
    "optimal",
    "robust",
    "efficient",
    "normal",
    "as needed",
    "where possible",
]

UNRESOLVED_MARKERS = ["待确认", "TBD", "待定", "待补充", "TODO", "???"]

_HEADING_RE = re.compile(r"^\s*h[1-6]\.\s+")
_ENTRY_RE = re.compile(r"^\s*[*#-]\s+\S")


def split_sections(text):
    """把 wiki markup 文本按 h1.~h6. 标题切成 ``{标题: 正文}``。"""
    sections = {}
    current = None
    buffer = []
    for line in text.splitlines():
        if _HEADING_RE.match(line):
            if current is not None:
                sections[current] = "\n".join(buffer)
            current = _HEADING_RE.sub("", line).strip()
            buffer = []
        elif current is not None:
            buffer.append(line)
    if current is not None:
        sections[current] = "\n".join(buffer)
    return sections


def count_entries(body):
    """统计列表条目数（``* x`` / ``# x`` / ``- x``）。"""
    return sum(1 for line in body.splitlines() if _ENTRY_RE.match(line))


def _find_section(sections, keywords):
    for title, body in sections.items():
        lowered = title.lower()
        if any(keyword in lowered for keyword in keywords):
            return title, body
    return None, None


def _vague_terms_in(line):
    lowered = line.lower()
    hits = [term for term in VAGUE_TERMS_ZH if term in line]
    hits += [term for term in VAGUE_TERMS_EN if term in lowered]
    return hits


def lint_description(text, simple=False):
    """按撰写标准检查 description，返回 ``(errors, warnings)``。

    ``simple=True``（``--simple``）时跳过必备小节检查，只要求描述非空；
    禁用词与未确认标记仍然提示——简单任务不该被模板拖住，但也不该写出
    无法验收的条目。
    """
    errors, warnings = [], []
    if not text or not text.strip():
        errors.append("description 为空。至少写清『要做什么 + 期望结果』。")
        return errors, warnings

    sections = split_sections(text)
    if not sections and not simple:
        warnings.append("未检测到任何 h1.~h6. 小节标题，建议按模板分节（如 h2. Background & Goals）。")

    if not simple:
        for label, keywords in REQUIRED_SECTIONS:
            title, _ = _find_section(sections, keywords)
            if title is None:
                errors.append("缺少必备小节「%s」。" % label)

    title, body = _find_section(sections, REQUIRED_SECTIONS[2][1])
    if title is not None and count_entries(body) == 0:
        warnings.append("「%s」下没有任何列表条目，需求不可执行。" % title)

    title, body = _find_section(sections, REQUIRED_SECTIONS[3][1])
    if title is not None:
        entries = count_entries(body)
        if not simple and entries < 2:
            warnings.append("「%s」只有 %d 条，验收标准应可逐条判定通过/失败。" % (title, entries))
        for line in body.splitlines():
            hits = _vague_terms_in(line)
            if hits and not re.search(r"\d", line):
                warnings.append(
                    "「%s」含无法判定的表述 %s：%s —— 改为可量化、可测试的条目。"
                    % (title, hits, line.strip()[:60])
                )

    if not simple:
        for label, keywords in OPTIONAL_SECTIONS:
            found, _ = _find_section(sections, keywords)
            if found is None:
                warnings.append("建议补充小节「%s」（确实无内容可写「无」）。" % label)

    unresolved = sum(text.count(marker) for marker in UNRESOLVED_MARKERS)
    if unresolved:
        warnings.append(
            "description 中有 %d 处未确认标记（待确认/TBD）。确认这些内容已与用户明确，"
            "而不是 agent 自己填的假设。" % unresolved
        )

    return errors, warnings
