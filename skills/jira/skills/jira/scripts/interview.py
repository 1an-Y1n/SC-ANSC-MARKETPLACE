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

"""Interview questions for ``--interview``.

The question list is derived from the description template, not from a minimal
set: four required sections map to four mandatory questions, so the interview
cannot produce a description that only covers three of them. Two optional
follow-ups cover the recommended sections and may be skipped.

Each question carries a hint, an example and a counter-example. The user's
pain point is "I don't know what to write", so the wording is part of the
feature, not documentation.
"""

from jira_fields import issue_type_fields

REQUIRED_QUESTIONS = [
    {
        "section": "Background & Goals",
        "question": "这次要解决什么现状问题？做成之后，什么现象算「成了」？",
        "hint": "写现状 + 目标，不要写实现方案。",
        "example": "HS 模式下 EQ 频点跨度写死 80 MHz，现场无法按信道规划调整。"
        "目标：新增可配置项，默认值不变，非法值回退默认。",
        "counter_example": "「优化系统」「提升体验」——现状和目标都是空的。",
    },
    {
        "section": "User Story",
        "question": "谁在什么场景下用？现在他们怎么做？新能力替代哪一步？",
        "hint": "角色 + 场景 + 价值；纯内部重构就写「作为维护者」。",
        "example": "作为现场调试工程师，在部署前按当地信道规划调整 EQ 频点跨度，"
        "替代现在改代码重编固件的做法。",
        "counter_example": "「作为用户，我希望系统更好用」——角色和场景都空。",
    },
    {
        "section": "Requirements",
        "question": "要做哪些功能点？哪些明确不做？异常路径怎么处理？",
        "hint": "逐条列；边界和异常比正常流程更重要。",
        "example": "1) 新增 eq_span_hs，20–160 MHz，步进 5；2) 未配置时用 80；"
        "3) 非法值启动报错并回退。不做：运行时热更新。",
        "counter_example": "只写「支持配置」——没有范围、没有边界。",
    },
    {
        "section": "Acceptance Criteria",
        "question": "每条怎么判定通过/失败？有没有量化指标？谁来验、怎么验？",
        "hint": "二值可判定；覆盖正常路径 + 关键异常；3~8 条。",
        "example": "eq_span_hs=40 时抓包确认间隔 40 MHz；=200 时日志报 invalid 且实际用 80；"
        "不配置时行为与改动前一致。",
        "counter_example": "「性能良好」「功能正常」——无法判定。",
    },
]

OPTIONAL_QUESTIONS = [
    {
        "section": "Technical Notes",
        "question": "涉及哪些模块/接口/数据结构？会影响哪些既有功能？（不知道可跳过）",
        "hint": "可以只写你确定的部分。",
        "example": "mamba_eq.c、配置解析模块；影响 HS 模式初始化路径。",
        "counter_example": "「涉及相关模块」——等于没写。",
    },
    {
        "section": "Dependencies & Risks",
        "question": "有前置依赖、外部系统或已知风险吗？（不知道可跳过）",
        "hint": "没有就写「无」，不要留空。",
        "example": "依赖 DZ300-118 的配置框架；风险：旧配置文件没有该字段时需要兼容。",
        "counter_example": "留空——评审时无法判断是「没有」还是「没想」。",
    },
]

# CLI 已经负责的字段，不再作为「项目必填」追问
CLI_HANDLED_FIELDS = {
    "project",
    "issuetype",
    "summary",
    "description",
    "priority",
    "assignee",
    "labels",
    "components",
    "timetracking",
    "duedate",
    "parent",
}


def build_questions(issue_type="Story"):
    """返回访谈的完整问题集（不含项目必填字段，由调用方补）。"""
    return {
        "mode": "interview",
        "issue_type": issue_type,
        "required": REQUIRED_QUESTIONS,
        "optional": OPTIONAL_QUESTIONS,
        "project_fields": [],
        "project_fields_error": "",
    }


def project_field_questions(meta, issue_type):
    """从归一化的 create meta 提取需要用户提供的必填字段。

    ``required && !hasDefaultValue`` 且不在 ``CLI_HANDLED_FIELDS`` 里的字段，
    建单时不会自动填，必须问出来。

    返回 ``(questions, error)``：类型名按大小写不敏感匹配（与建单路径共用
    ``jira_fields.issue_type_fields()``）；类型不在 meta 里时 ``error`` 非空，
    调用方应把它写进 ``project_fields_error``，而不是静默当作「没有必填字段」。
    """
    type_fields = issue_type_fields(meta.get("fields_by_issue_type", {}), issue_type)
    if type_fields is None:
        available = [it.get("name") for it in meta.get("issue_types", []) if it.get("name")]
        return [], "issue type %r 不在可用列表: %s" % (issue_type, ", ".join(available) or "(空)")
    questions = []
    for field_id, field in (type_fields or {}).items():
        if not isinstance(field, dict):
            continue
        if field_id in CLI_HANDLED_FIELDS:
            continue
        if field.get("required") and not field.get("hasDefaultValue"):
            name = field.get("name") or field_id
            questions.append(
                {
                    "section": "项目必填字段",
                    "field_id": field_id,
                    "name": name,
                    "question": "`%s (%s)` 是项目必填字段，值从哪来？" % (name, field_id),
                    "required": True,
                }
            )
    return questions, ""


def render_markdown(payload):
    """把问题集渲染成给人看的 markdown。"""
    issue_type = payload.get("issue_type") or "Story"
    lines = ["# %s 建单访谈" % issue_type, ""]
    lines.append("先回答下面 4 个必答问题，再决定要不要补 2 个可选项。")
    lines.append("")

    lines.append("## 必答")
    lines.append("")
    for index, item in enumerate(payload.get("required", []), start=1):
        lines.append("### %d. %s" % (index, item["section"]))
        lines.append("")
        lines.append("**问**：%s" % item["question"])
        lines.append("")
        lines.append("**提示**：%s" % item["hint"])
        lines.append("")
        lines.append("**例**：%s" % item["example"])
        lines.append("")
        lines.append("**反例**：%s" % item["counter_example"])
        lines.append("")

    lines.append("## 可选追问（不知道就跳过）")
    lines.append("")
    for index, item in enumerate(payload.get("optional", []), start=len(payload.get("required", [])) + 1):
        lines.append("### %d. %s" % (index, item["section"]))
        lines.append("")
        lines.append("**问**：%s" % item["question"])
        lines.append("")
        lines.append("**提示**：%s" % item["hint"])
        lines.append("")
        lines.append("**例**：%s" % item["example"])
        lines.append("")
        lines.append("**反例**：%s" % item["counter_example"])
        lines.append("")

    project_fields = payload.get("project_fields") or []
    if project_fields:
        lines.append("## 项目必填字段")
        lines.append("")
        for item in project_fields:
            lines.append("- %s" % item["question"])
        lines.append("")

    if payload.get("project_fields_error"):
        lines.append("## 项目必填字段校验未完成")
        lines.append("")
        lines.append("- %s" % payload["project_fields_error"])
        lines.append("")

    return "\n".join(lines).rstrip() + "\n"
