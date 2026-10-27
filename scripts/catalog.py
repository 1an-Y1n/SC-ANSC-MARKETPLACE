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

"""
scripts/catalog.py — ai-toolbox 条目元数据的校验与目录生成

仓库是唯一真源。每个条目在自己的 README.md / SKILL.md 顶部用 YAML front-matter
声明元数据；本脚本据此校验（check）、生成 README 的目录表与 Confluence 页面
payload（build）、发布到 Confluence（publish）。条目 README 里的维护者那一行也由
front-matter 的 maintainers 渲染，落在 maintainer 标记对之间。

用法 / Usage:
    ./scripts/catalog.py check                  # 只校验元数据与 README 目录表（只读，离线）
    ./scripts/catalog.py check --remote         # 额外比对 Confluence 页面是否漂移（只读）
    ./scripts/catalog.py build                  # 打印将要写入的内容，不落盘（dry-run）
    ./scripts/catalog.py build --apply          # 写回 README 目录表 + 各条目的维护者行 + 生成 payload
    ./scripts/catalog.py publish                # 打印将要发布什么，不写 Confluence（dry-run）
    ./scripts/catalog.py publish --apply        # 真正写入 Confluence
    ./scripts/catalog.py sync                   # build + publish 一次跑完（dry-run）
    ./scripts/catalog.py sync --apply           # 一条命令：重写 README 目录表 + 更新 Confluence
    ./scripts/catalog.py bump <条目>            # 给某个条目升一级版本号（默认 patch）
    ./scripts/catalog.py bump <条目> --minor    # 也可以 --major / --patch

依赖 / Dependencies:
    Python >= 3.8、PyYAML、requests（仅 publish / check --remote 需要）
    检查: python3 -c "import yaml, requests; print(yaml.__version__, requests.__version__)"
    安装: pip3 install PyYAML requests

Confluence 凭据 / Credentials:
    从 ~/.config/windsurf/jira_config.json 读 confluence_url / confluence_token
    （可用环境变量 CATALOG_CONFLUENCE_CONFIG 指向别的文件）。凭据不进版本库。

退出码 / Exit codes:
    0  成功（build / publish 的 dry-run 也返回 0）
    1  check 发现校验错误，或 check --remote 发现漂移
    2  用法 / 前置条件错误（缺配置、缺依赖、缺凭据）
    3  publish 被拒绝或写入失败
"""

import argparse
import contextlib
import hashlib
import io
import json
import os
import re
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parent.parent
CONFIG_PATH = REPO_ROOT / "scripts" / "catalog.config.json"
README_PATH = REPO_ROOT / "README.md"
PAYLOAD_DIR = REPO_ROOT / ".devin" / "TmpWorkDir" / "catalog"

# (目录, 元数据文件名, 该目录下的默认 type)
# `.devin/skills/` 不在其中：它是同步脚本的产物目录（派生副本），不是发布源。
ENTRY_ROOTS = (
    ("skills", "README.md", "skill"),
    ("mcp", "README.md", "mcp"),
    ("tools", "README.md", "tool"),
)

REQUIRED_FIELDS = (
    "name",
    "type",
    "version",
    "title_zh",
    "summary_zh",
    "summary_en",
    "scenario",
    "entry",
    "install",
    "deps",
    "upstream",
    "maintainers",
)

VALID_TYPES = ("skill", "mcp", "tool", "doc")

# 受控场景词表：条目只能从这里挑，总览页按 id 聚合
SCENARIOS = {
    "commit": ("提交代码到 Gerrit", "Commit code to Gerrit"),
    "code-review": ("审查 Gerrit 代码改动", "Review code changes in Gerrit"),
    "jira": ("查 / 建 Jira 工单、读写 Confluence", "Look up or create Jira issues, read and write Confluence"),
    "notify": ("发邮件通知", "Send email notifications"),
    "design-review": ("动手前拷问方案", "Stress-test a plan before coding"),
    "code-graph": ("给 agent 一张代码知识图谱", "Give the agent a code knowledge graph"),
    "ai-automation": ("AI自动化处理工具", "AI Automation Tools"),
}

TYPE_ORDER = {"skill": 0, "mcp": 1, "tool": 2, "doc": 3}

# Confluence 类别页（标题 = type 大写）的一句话说明；没列出的 type 用兜底文案
CATEGORY_INTRO = {
    "skill": (
        "给 AI agent 装的技能：提示词、脚本、小工具，放进 agent 的 skill 目录即生效。",
        "Skills you install into your AI agent — prompts, scripts, small tools.",
    ),
    "mcp": (
        "给 AI agent 接的 MCP 服务器：通过 MCP 协议给 agent 提供工具与数据。",
        "MCP servers your AI agent connects to — tools and data over the Model Context Protocol.",
    ),
    "tool": (
        "常驻工具：cron / daemon 之类独立运行的自动化服务，不装进 agent。",
        "Resident tools — cron/daemon-style services that run on their own, outside the agent.",
    ),
    "doc": (
        "仓库文档与使用手册。",
        "Repository docs and manuals.",
    ),
}

README_BEGIN = "<!-- catalog:begin -->"
README_END = "<!-- catalog:end -->"

# 条目 README 里维护者那一行的标记对：内容由 front-matter 的 maintainers 渲染后注入
MAINTAINER_BEGIN = "<!-- maintainer:begin -->"
MAINTAINER_END = "<!-- maintainer:end -->"

# Confluence 侧
CONFLUENCE_LABEL = "ai-toolbox-catalog"
CONFLUENCE_CONFIG = Path(
    os.environ.get("CATALOG_CONFLUENCE_CONFIG", "~/.config/windsurf/jira_config.json")
).expanduser()
ORPHAN_BANNER = "此条目已从仓库移除"
# 内容哈希存在页面属性里：Confluence 会剥掉 storage 正文里的 HTML 注释，放正文里存不住
PROPERTY_KEY = "catalog"

FRONT_MATTER_RE = re.compile(r"\A---\r?\n(.*?)\r?\n---\r?\n", re.DOTALL)
# 版本号：严格 semver（x.y.z），每个条目各有一份，互不影响
SEMVER_RE = re.compile(r"^\d+\.\d+\.\d+$")
# maintainers 列表里每一项的写法：`名字 <邮箱>`
MAINTAINER_RE = re.compile(r"^(?P<name>.+?)\s*<(?P<email>[^<>@\s]+@[^<>\s]+)>$")
# bump 时定位 front-matter 里那一行 version（不吞掉行尾换行）
VERSION_LINE_RE = re.compile(r"^version:[ \t]*(\S+)[ \t]*$", re.MULTILINE)
HEADING_RE = re.compile(r"^(#{1,6})\s")
# 「粘给 AI」提示词所在的段落标题
AI_PROMPT_HEADING_RE = re.compile(r"^#{2,4}\s.*(让 AI 装|let your AI agent)", re.IGNORECASE)
# 「为什么值得装」所在的段落标题（编号与否都认，如 `## 2. 为什么值得装`）
WORTH_HEADING_RE = re.compile(r"^#{2}\s*(?:\d+\.\s*)?为什么值得装")
# 「一键安装」所在的段落标题（编号与否都认，如 `## 4. 一键安装`）
INSTALL_HEADING_RE = re.compile(r"^#{2}\s*(?:\d+\.\s*)?一键安装")
# 「升级」所在的段落标题（编号与否都认，如 `### 升级 / Upgrade`）
UPGRADE_HEADING_RE = re.compile(r"^#{2,4}\s*(?:\d+\.\s*)?升级\s*/\s*Upgrade")
# 「让 AI 查更新 / 升级」提示词所在的段落标题 —— 单独写，别并进 AI_PROMPT_HEADING_RE：
# 那个正则取的是「让 AI 装」的两个块，混进来会把安装提示词挤掉
UPGRADE_PROMPT_HEADING_RE = re.compile(
    r"^#{2,4}\s.*(让 AI 查更新|Have your AI check for updates)", re.IGNORECASE
)
# 「仅项目级」说明文档检查步骤的标记：提示词块里出现 --project（支持项目级安装）的条目，
# 安装 / 升级提示词必须含这一步 —— 看安装目录下的说明文档（如 .devin/skills/README.md）要不要跟着更新。
# 三个标记取合取，避免无关行文碰巧含其一就放行（启发式兜底，残余局限见 scripts/catalog.md）
PROJECT_DOC_STEP_RE = re.compile(r"仅项目级|project level only", re.IGNORECASE)
PROJECT_DOC_PATH_RE = re.compile(r"\.devin/skills/")
# 同一步骤里必须提到的说明文档名
README_DOC_RE = re.compile(r"README", re.IGNORECASE)
# 提示词里禁止出现的固定共享克隆目录：多人同机同时安装会撞（/tmp 的 sticky 位还让后到者删不掉它）
FIXED_TMP_LITERAL = "/tmp/ai-toolbox"
# 条目之外也要一起扫的文件：模板不是条目（`_` 开头），SHARE.md 不在 front-matter 体系内
GUARD_EXTRA_DOCS = (
    "skills/_template/README.md",
    "skills/_template/SHARE.md",
)


def read_front_matter(path):
    """读取文件顶部的 YAML front-matter；没有则返回 None。"""
    text = path.read_text(encoding="utf-8")
    match = FRONT_MATTER_RE.match(text)
    if not match:
        return None
    return yaml.safe_load(match.group(1)) or {}


def split_maintainer(raw):
    """把 `名字 <邮箱>` 拆成 (名字, 邮箱)；不符合这个写法则返回 None。"""
    match = MAINTAINER_RE.match(str(raw).strip())
    if not match:
        return None
    return match.group("name").strip(), match.group("email").strip()


def readme_ai_prompts(path):
    """从条目文档里提取「粘给 AI」的提示词块，返回 [中文块, 英文块(可选)]。

    约定：在标题含「让 AI 装 / let your AI agent」的那一段里，用 ```text 代码块
    写提示词，中英各一段就写两个块；取到下一个同级或更高级标题为止。
    这样 README 是唯一真源 —— 改 README，Confluence 页面跟着变。
    """
    if not path.is_file():
        return []
    lines = path.read_text(encoding="utf-8").splitlines()
    start = level = None
    for index, line in enumerate(lines):
        if AI_PROMPT_HEADING_RE.match(line):
            start, level = index, len(HEADING_RE.match(line).group(1))
            break
    if start is None:
        return []

    blocks, current = [], None
    for line in lines[start + 1 :]:
        heading = HEADING_RE.match(line)
        if heading and len(heading.group(1)) <= level:
            break
        if line.strip() == "```text":
            current = []
        elif line.strip() == "```" and current is not None:
            blocks.append("\n".join(current))
            current = None
        elif current is not None:
            current.append(line)
    return blocks


def readme_worth_section(path):
    """从条目文档里提取「为什么值得装」一节的正文行（不含标题行），没有则返回 []。

    约定：`## 为什么值得装`（编号与否均可），取到下一个同级或更高级标题为止；
    尾部的 `---` 分隔线与空行不算正文。README 是唯一真源 —— 改 README，Confluence 页面跟着变。
    """
    if not path.is_file():
        return []
    lines = path.read_text(encoding="utf-8").splitlines()
    start = None
    for index, line in enumerate(lines):
        if WORTH_HEADING_RE.match(line):
            start = index
            break
    if start is None:
        return []
    body = []
    for line in lines[start + 1 :]:
        heading = HEADING_RE.match(line)
        if heading and len(heading.group(1)) <= 2:
            break
        body.append(line)
    while body and body[-1].strip() in ("", "---"):
        body.pop()
    return body


def readme_install_block(path):
    """从条目文档里提取「一键安装」段里的第一个 ```bash 代码块；没有则返回 None。

    约定：标题含「一键安装」的那一段里，第一个 ```bash 块就是安装步骤，取到下一个
    同级或更高级标题为止。README 是唯一真源 —— 改 README，Confluence 页面跟着变。
    """
    if not path.is_file():
        return None
    lines = path.read_text(encoding="utf-8").splitlines()
    start = None
    for index, line in enumerate(lines):
        if INSTALL_HEADING_RE.match(line):
            start = index
            break
    if start is None:
        return None
    block = None
    for line in lines[start + 1 :]:
        heading = HEADING_RE.match(line)
        if heading and len(heading.group(1)) <= 2:
            break
        if line.strip() == "```bash":
            block = []
        elif line.strip() == "```" and block is not None:
            break
        elif block is not None:
            block.append(line)
    if not block:
        return None
    return "\n".join(block).strip() or None


def readme_upgrade_prompts(path):
    """从条目文档里提取「让 AI 查更新 / 升级」的提示词块，返回 [中文块, 英文块(可选)]。

    约定与 readme_ai_prompts 相同，只是匹配另一个标题：标题含「让 AI 查更新」或
    「Have your AI check for updates」的那一段里，用 ```text 代码块中英各写一段。
    """
    if not path.is_file():
        return []
    lines = path.read_text(encoding="utf-8").splitlines()
    start = level = None
    for index, line in enumerate(lines):
        if UPGRADE_PROMPT_HEADING_RE.match(line):
            start, level = index, len(HEADING_RE.match(line).group(1))
            break
    if start is None:
        return []

    blocks, current = [], None
    for line in lines[start + 1 :]:
        heading = HEADING_RE.match(line)
        if heading and len(heading.group(1)) <= level:
            break
        if line.strip() == "```text":
            current = []
        elif line.strip() == "```" and current is not None:
            blocks.append("\n".join(current))
            current = None
        elif current is not None:
            current.append(line)
    return blocks


def readme_upgrade_block(path):
    """从条目文档里提取「升级」段里的第一个 ```bash 代码块；没有则返回 None。

    约定：标题含「升级 / Upgrade」的那一段里，第一个 ```bash 块就是升级步骤（重跑安装即
    升级、`check-remote` 查远端），取到下一个同级或更高级标题为止。
    """
    if not path.is_file():
        return None
    lines = path.read_text(encoding="utf-8").splitlines()
    start = level = None
    for index, line in enumerate(lines):
        if UPGRADE_HEADING_RE.match(line):
            start, level = index, len(HEADING_RE.match(line).group(1))
            break
    if start is None:
        return None
    block = None
    for line in lines[start + 1 :]:
        heading = HEADING_RE.match(line)
        if heading and len(heading.group(1)) <= level:
            break
        if line.strip() == "```bash":
            block = []
        elif line.strip() == "```" and block is not None:
            break
        elif block is not None:
            block.append(line)
    if not block:
        return None
    return "\n".join(block).strip() or None


def git_clone_blocks(path):
    """收集文件里所有以 `git clone` 开头的 ```bash 代码块（用于 SHARE.md 与 README 比对）。"""
    if not path.is_file():
        return []
    blocks, current = [], None
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip() == "```bash":
            current = []
        elif line.strip() == "```" and current is not None:
            if current and current[0].strip().startswith("git clone"):
                blocks.append("\n".join(current).strip())
            current = None
        elif current is not None:
            current.append(line)
    return blocks


def read_maintainer_block(path):
    """读取条目文档里 maintainer 标记对之间的内容（已 strip）；标记缺失则返回 None。

    README 是唯一真源 —— 改 front-matter 的 maintainers，跑 build --apply 重写这一段。
    """
    if not path.is_file():
        return None
    text = path.read_text(encoding="utf-8")
    start = text.find(MAINTAINER_BEGIN)
    end = text.find(MAINTAINER_END)
    if start < 0 or end < 0 or end < start:
        return None
    return text[start + len(MAINTAINER_BEGIN) : end].strip()


def fixed_tmp_error(path):
    """文件里出现固定共享克隆目录就返回一条可执行的错误说明，否则返回 None。"""
    if not path.is_file() or FIXED_TMP_LITERAL not in path.read_text(encoding="utf-8"):
        return None
    return (
        f"{path.relative_to(REPO_ROOT)}: 出现固定路径 {FIXED_TMP_LITERAL} —— 多人同机同时安装会互相冲突"
        "（/tmp 有 sticky 位，后到者还删不掉先到者的目录）。改成每次唯一的临时目录："
        'workdir="$(mktemp -d "${TMPDIR:-/tmp}/ai-toolbox.XXXXXX")"，后续步骤用 "$workdir/..."'
    )


def load_config():
    """读取 scripts/catalog.config.json。"""
    if not CONFIG_PATH.is_file():
        fail(2, f"缺少配置文件 / missing config: {CONFIG_PATH}")
    return json.loads(CONFIG_PATH.read_text(encoding="utf-8"))


def collect_entries():
    """扫描所有条目目录，返回 [{name, path, type, dir, meta_file, meta}]，按 type/name 排序。

    只扫 ENTRY_ROOTS 里的发布源；`.devin/skills/` 是同步脚本的产物目录，其中的 skill
    不进目录表、也不参与 check —— 本仓自用的 skill 放那里即可。
    """
    entries = []
    for rel_dir, meta_file, dir_type in ENTRY_ROOTS:
        root = REPO_ROOT / rel_dir
        if not root.is_dir():
            continue
        for child in sorted(root.iterdir()):
            if not child.is_dir() or child.name.startswith("_"):
                # 下划线开头不是条目（如 skills/_template）—— 目录名即约定
                continue
            meta_path = child / meta_file
            meta = read_front_matter(meta_path) if meta_path.is_file() else None
            entries.append(
                {
                    "name": child.name,
                    "path": f"{rel_dir}/{child.name}",
                    "dir": child,
                    "meta_file": meta_file,
                    "meta_path": meta_path,
                    "dir_type": dir_type,
                    "meta": meta,
                }
            )
    entries.sort(key=lambda e: (TYPE_ORDER.get(e["dir_type"], 9), e["name"]))
    return entries


def project_doc_step_errors(where, path):
    """检查「粘给 AI」提示词块里的项目级说明文档步骤，返回错误列表。

    约定：提示词块里出现 `--project`（支持项目级安装的条目），「让 AI 装」与
    「让 AI 查更新 / 升级」的每个提示词块都必须含「仅项目级看安装目录说明文档」
    那一步 —— 按三个标记的合取判定：「仅项目级」（英文块 project level only）
    + `.devin/skills/` + README；没有项目级安装的条目（提示词里没有 --project）
    不受约束。规则本身由 project_doc_rule_selftest 用 fixture 守护。
    """
    errors = []
    for section, blocks in (
        ("让 AI 装", readme_ai_prompts(path)),
        ("让 AI 查更新 / 升级", readme_upgrade_prompts(path)),
    ):
        if not any("--project" in block for block in blocks):
            continue
        if any(
            not (
                PROJECT_DOC_STEP_RE.search(block)
                and PROJECT_DOC_PATH_RE.search(block)
                and README_DOC_RE.search(block)
            )
            for block in blocks
        ):
            errors.append(
                f"{where}: {section}的提示词块里有 --project（支持项目级安装），但缺"
                "「仅项目级检查安装目录说明文档」那一步 —— 照 skills/_template/README.md 里的"
                "「（仅项目级）看工程仓的 .devin/skills/ 下有没有说明文档要跟着更新」补上，"
                "中英块都要有（标记：仅项目级 / project level only + .devin/skills/ + README）"
            )
    return errors


SELFTEST_INSTALL_HEADING = "### 不想手动敲命令？让 AI 装 / Or let your AI agent do it"
SELFTEST_UPGRADE_HEADING = "### 让 AI 查更新 / 升级 / Have your AI check for updates"


def project_doc_rule_selftest():
    """project_doc_step_errors 的自测：临时 fixture 验证规则会拦、也会放行。

    负例：安装与升级两个提示词块都含 --project、都缺标记 → 必须各报一条错；
    正例：两个块都带齐三个标记 → 必须无错。规则、标记正则或块提取函数
    将来被改坏时，check 在这里大声失败，而不是静默放行（fail-open）。
    """
    negative = (
        f"{SELFTEST_INSTALL_HEADING}\n\n```text\n0. 跑 ./install.sh --project <repo>\n```\n\n"
        f"{SELFTEST_UPGRADE_HEADING}\n\n```text\n1. 升级：./install.sh upgrade --project <repo>\n```\n"
    )
    positive = (
        f"{SELFTEST_INSTALL_HEADING}\n\n```text\n"
        "0.（仅项目级）看工程仓的 .devin/skills/ 下有没有说明文档要跟着更新（README.md 等）\n"
        "1. 跑 ./install.sh --project <repo>\n```\n\n"
        f"{SELFTEST_UPGRADE_HEADING}\n\n```text\n"
        "1.（仅项目级）升级后核对工程仓 .devin/skills/ 里的说明文档（README.md 等）\n"
        "2. 升级：./install.sh upgrade --project <repo>\n```\n"
    )
    errors = []
    with tempfile.TemporaryDirectory() as tmp:
        for label, text, expected in (("negative", negative, 2), ("positive", positive, 0)):
            path = Path(tmp) / f"selftest-{label}.md"
            path.write_text(text, encoding="utf-8")
            found = project_doc_step_errors("selftest", path)
            if len(found) != expected:
                errors.append(
                    f"project_doc_rule 自测失败：{label} fixture 预期 {expected} 条错误，"
                    f"实际 {len(found)} 条：{'；'.join(found) or '（无）'}"
                )
    return errors


def validate(entries):
    """校验全部条目的元数据，返回错误信息列表（空列表 = 通过）。"""
    errors = []
    seen = {}

    for entry in entries:
        where = entry["path"]
        meta = entry["meta"]

        if meta is None:
            errors.append(
                f"{where}: 缺少 front-matter —— 请在 {entry['meta_file']} 顶部加一个 YAML 块"
            )
            continue

        for field in REQUIRED_FIELDS:
            value = meta.get(field)
            if value is None or (isinstance(value, str) and not value.strip()):
                errors.append(f"{where}: 缺字段 `{field}`")

        name = meta.get("name")
        if name and name != entry["name"]:
            errors.append(f"{where}: `name` 是 `{name}`，与目录名 `{entry['name']}` 不一致")
        if name:
            if name in seen:
                errors.append(f"{where}: `name` 与 {seen[name]} 重复")
            else:
                seen[name] = where

        etype = meta.get("type")
        if etype and etype not in VALID_TYPES:
            errors.append(f"{where}: `type` 是 `{etype}`，合法值 {list(VALID_TYPES)}")
        if etype and etype != entry["dir_type"]:
            errors.append(
                f"{where}: `type` 是 `{etype}`，但目录 `{entry['path'].rsplit('/', 1)[0]}/` 表示 `{entry['dir_type']}`"
            )

        version = meta.get("version")
        if version is not None and (
            not isinstance(version, str) or not SEMVER_RE.match(version.strip())
        ):
            errors.append(
                f"{where}: `version` 是 `{version}`，必须是严格 semver（x.y.z），例如 1.0.0"
                "（注意别写成 1.0 —— 那样 YAML 会当数字解析）"
            )

        scenario = meta.get("scenario")
        if scenario is not None and not isinstance(scenario, list):
            errors.append(f"{where}: `scenario` 必须是列表，例如 [commit, jira]")
        elif isinstance(scenario, list):
            for sid in scenario:
                if sid not in SCENARIOS:
                    errors.append(
                        f"{where}: `scenario` 里的 `{sid}` 不在受控词表 {sorted(SCENARIOS)}"
                    )

        deps = meta.get("deps")
        if deps is not None and not isinstance(deps, list):
            errors.append(f"{where}: `deps` 必须是列表；没有外部依赖就写 []")

        maintainers = meta.get("maintainers")
        maintainers_ok = isinstance(maintainers, list) and bool(maintainers)
        if maintainers is not None and not isinstance(maintainers, list):
            errors.append(
                f"{where}: `maintainers` 必须是列表，例如 [Argon Cheng <argon_cheng@sercomm.com>]"
            )
            maintainers_ok = False
        elif maintainers_ok:
            for raw in maintainers:
                if not isinstance(raw, str) or not split_maintainer(raw):
                    errors.append(
                        f"{where}: `maintainers` 里的 `{raw}` 不是 `名字 <邮箱>` 形式，"
                        "例如 Argon Cheng <argon_cheng@sercomm.com>"
                    )
                    maintainers_ok = False
        elif maintainers == []:
            errors.append(f"{where}: `maintainers` 是空列表 —— 至少写一个 `名字 <邮箱>`")

        if maintainers_ok:
            line = render_maintainer_line(entry)
            block = read_maintainer_block(entry["meta_path"])
            if block is None:
                errors.append(
                    f"{where}: {entry['meta_file']} 里缺维护者标记对 —— 在标题引文块之后加"
                    f" `{MAINTAINER_BEGIN}` / `{MAINTAINER_END}` 两行，"
                    "再跑 ./scripts/catalog.py build --apply 自动填内容"
                )
            elif block != line:
                errors.append(
                    f"{where}: README 里的维护者行与 front-matter 的 `maintainers` 不一致 —— "
                    "跑 ./scripts/catalog.py build --apply 重写"
                )

        install = meta.get("install")
        if install and install != "none" and not readme_ai_prompts(entry["meta_path"]):
            errors.append(
                f"{where}: 缺「粘给 AI」的提示词块 —— Confluence 子页上会少一整段。"
                f"在 {entry['meta_file']} 里加一段"
                " `### 不想手动敲命令？让 AI 装 / Or let your AI agent do it`，"
                "下面放 ```text 代码块（中英各一段）"
            )
        errors.extend(project_doc_step_errors(where, entry["meta_path"]))

        if not readme_worth_section(entry["meta_path"]):
            errors.append(
                f"{where}: 缺「为什么值得装」一节 —— 读者要先看到装它的理由才会想装。"
                f"在 {entry['meta_file']} 的「这是什么」之后加一段"
                " `## 为什么值得装 / Why it's worth it`（模板有现成的），"
                "按「解决什么痛点 / 不装会怎样 / 适合谁·不适合谁」三问写"
            )

        install_block = readme_install_block(entry["meta_path"])
        if install and install != "none" and install_block is None:
            errors.append(
                f"{where}: 缺「一键安装」代码块 —— Confluence 子页上会退化成老拼法。"
                f"在 {entry['meta_file']} 的 `## 一键安装 / One-command install` 段下放一个"
                " ```bash 块（页面上的「怎么装」就是照搬它）"
            )

        if install_block is not None:
            for block in git_clone_blocks(entry["dir"] / "SHARE.md"):
                if block != install_block:
                    errors.append(
                        f"{where}: SHARE.md 里的安装块与 README 的不一致 —— 两处是同一段文案，"
                        "改成逐字相同（README 是唯一真源）"
                    )
                    break

        for target in (entry["meta_path"], entry["dir"] / "SHARE.md"):
            message = fixed_tmp_error(target)
            if message:
                errors.append(message)

    for rel in GUARD_EXTRA_DOCS:
        message = fixed_tmp_error(REPO_ROOT / rel)
        if message:
            errors.append(message)
    errors.extend(
        project_doc_step_errors(
            "skills/_template/README.md", REPO_ROOT / "skills/_template/README.md"
        )
    )
    errors.extend(project_doc_rule_selftest())
    errors.extend(check_order_selftest())
    errors.extend(beta_render_selftest())

    return errors


def maintainer_md(meta):
    """把 maintainers 渲染成 Markdown（名字 + mailto 链接）；多人用 <br> 分隔。"""
    items = []
    for raw in meta.get("maintainers") or []:
        pair = split_maintainer(raw)
        if pair:
            items.append(f"{pair[0]} [{pair[1]}](mailto:{pair[1]})")
    return "<br>".join(items)


def maintainer_html(meta):
    """把 maintainers 渲染成 Confluence storage 行内 HTML；多人用 <br/> 分隔。"""
    items = []
    for raw in meta.get("maintainers") or []:
        pair = split_maintainer(raw)
        if pair:
            items.append(f'{escape(pair[0])} <a href="mailto:{escape(pair[1])}">{escape(pair[1])}</a>')
    return "<br/>".join(items)


def render_maintainer_line(entry):
    """渲染条目 README 里注入的维护者那一行。"""
    return f"> 维护者 / Maintainer：{maintainer_md(entry['meta'])}"


def is_prerelease(version):
    """0.x 视为测试版；validate 已保证 version 是严格 semver。"""
    return bool(version) and version.split(".", 1)[0] == "0"


def version_badge(version):
    """Confluence 用的版本徽章；0.x 追加 beta 标记。"""
    suffix = ' <span class="cat-beta">· beta</span>' if is_prerelease(version) else ""
    return f'<span class="cat-ver">v{escape(version)}</span>{suffix}'


def version_text(version):
    """README 目录表用的纯文本版本；0.x 追加 beta 标记。"""
    return f"{version} · beta" if is_prerelease(version) else version


def render_readme_table(entries):
    """渲染 README 里的 6 列目录表（与现有形态一致）。"""
    lines = [
        "| 类型 | 条目 | 版本 | 一句话 | 位置 | 维护者 |",
        "| --- | --- | --- | --- | --- | --- |",
    ]
    for entry in entries:
        meta = entry["meta"] or {}
        lines.append(
            f"| {entry['dir_type']} | **{entry['name']}** | {version_text(meta.get('version', ''))} | "
            f"{meta.get('summary_zh', '')} | "
            f"[`{entry['path']}/`](./{entry['path']}/) | {maintainer_md(meta)} |"
        )
    return "\n".join(lines)


def replace_readme_table(text, table):
    """把 README 中 catalog 标记之间的内容替换成新表；标记缺失则抛 ValueError。"""
    start = text.find(README_BEGIN)
    end = text.find(README_END)
    if start < 0 or end < 0 or end < start:
        raise ValueError(f"README 里找不到 {README_BEGIN} / {README_END} 标记")
    return text[: start + len(README_BEGIN)] + "\n" + table + "\n" + text[end:]


def replace_maintainer_block(text, line):
    """把条目 README 里 maintainer 标记之间的内容替换成维护者那一行；标记缺失则抛 ValueError。"""
    start = text.find(MAINTAINER_BEGIN)
    end = text.find(MAINTAINER_END)
    if start < 0 or end < 0 or end < start:
        raise ValueError(f"README 里找不到 {MAINTAINER_BEGIN} / {MAINTAINER_END} 标记")
    return text[: start + len(MAINTAINER_BEGIN)] + "\n" + line + "\n" + text[end:]


def maintainer_line_changes(entries):
    """算出各条目 README 里维护者那一行的新内容，返回 [(路径, 新文本, 是否有变化)]。"""
    changes = []
    for entry in entries:
        path = entry["meta_path"]
        text = path.read_text(encoding="utf-8")
        try:
            new_text = replace_maintainer_block(text, render_maintainer_line(entry))
        except ValueError as exc:
            fail(1, f"{entry['path']}: {exc}")
        changes.append((path, new_text, new_text != text))
    return changes


def escape(text):
    """转义 XML 特殊字符。"""
    return str(text).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def inline(text):
    """把一段 Markdown 行内标记转成 Confluence storage 行内 HTML。"""
    out = escape(text)
    out = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", out)
    out = re.sub(r"`([^`]+)`", r"<code>\1</code>", out)
    out = re.sub(r"\[([^\]]+)\]\(([^)]+)\)", r'<a href="\2">\1</a>', out)
    return out


# Confluence 视觉主题色（方案 A3：多彩语义混搭 —— 按 SKILL蓝 / MCP紫 / TOOL绿 专属分色）
TYPE_THEME = {
    "skill": {"label": "SKILL", "color": "#0052CC"},
    "mcp": {"label": "MCP", "color": "#5243AA"},
    "tool": {"label": "TOOL", "color": "#006644"},
    "doc": {"label": "DOC", "color": "#42526E"},
}

CONFLUENCE_CSS = """
.cat-wrap { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "PingFang SC", "Microsoft YaHei", sans-serif; color: #172B4D; line-height: 1.65; }
.cat-hero { background: linear-gradient(135deg, #EBF3FF 0%, #F3F0FF 50%, #E9FBF2 100%); border: 1px solid #C0B6F2; border-left: 5px solid #0052CC; border-radius: 12px; padding: 18px 22px; margin: 6px 0 18px 0; box-shadow: 0 2px 6px rgba(9,30,66,0.04); }
.cat-hero-title { font-size: 17px; font-weight: 600; color: #172B4D; margin: 0 0 8px 0; display: flex; align-items: center; gap: 8px; flex-wrap: wrap; }
.cat-hero-sub { color: #42526E; font-size: 13.5px; margin: 6px 0 0 0; }
.cat-pills { margin-top: 12px; display: flex; flex-wrap: wrap; gap: 8px; align-items: center; }
.cat-pill { display: inline-block; padding: 3px 11px; border-radius: 999px; font-size: 12px; font-weight: 600; background: #FFFFFF; border: 1px solid #DFE1E6; color: #172B4D; }
.cat-badge { display: inline-block; padding: 3px 10px; border-radius: 999px; font-size: 11.5px; font-weight: 700; letter-spacing: 0.3px; vertical-align: middle; line-height: 1.4; }
.cat-badge-skill { background: #DEEBFF; color: #0747A6; border: 1px solid #B3D4FF; }
.cat-badge-mcp { background: #EAE6FF; color: #403294; border: 1px solid #C0B6F2; }
.cat-badge-tool { background: #E3FCEF; color: #006644; border: 1px solid #ABF5D1; }
.cat-badge-doc { background: #EBECF0; color: #42526E; border: 1px solid #C1C7D0; }
.cat-badge-scen { background: #F4F5F7; color: #42526E; border: 1px solid #DFE1E6; font-weight: 600; margin-right: 4px; }
.wiki-content table.cat-table, table.cat-table { width: 100%; border-collapse: separate !important; border-spacing: 0 !important; border: 1px solid #DFE1E6 !important; border-radius: 10px !important; overflow: hidden !important; margin: 12px 0 20px 0 !important; box-shadow: 0 1px 4px rgba(9,30,66,0.04); }
.wiki-content table.cat-table th, table.cat-table th { background-color: #E9F2FF !important; color: #0747A6 !important; font-weight: 600 !important; padding: 10px 14px !important; border-bottom: 1px solid #DFE1E6 !important; border-right: 1px solid rgba(9,30,66,0.06) !important; border-top: none !important; border-left: none !important; text-align: left; }
.wiki-content table.cat-table td, table.cat-table td { padding: 10px 14px !important; border-bottom: 1px solid #EBECF0 !important; border-right: 1px solid #F4F5F7 !important; border-top: none !important; border-left: none !important; vertical-align: middle; background-color: #FFFFFF; }
.wiki-content table.cat-table tr:nth-child(even) td, table.cat-table tr:nth-child(even) td { background-color: #FAFBFC; }
.wiki-content table.cat-table tr:hover td, table.cat-table tr:hover td { background-color: #F0F6FF !important; transition: background-color 0.12s ease; }
.wiki-content table.cat-table tr:last-child td, table.cat-table tr:last-child td { border-bottom: none !important; }
.wiki-content table.cat-table-skill th, table.cat-table-skill th { background-color: #DEEBFF !important; color: #0747A6 !important; }
.wiki-content table.cat-table-mcp th, table.cat-table-mcp th { background-color: #EAE6FF !important; color: #403294 !important; }
.wiki-content table.cat-table-tool th, table.cat-table-tool th { background-color: #E3FCEF !important; color: #006644 !important; }
.wiki-content table.cat-kv-table th, table.cat-kv-table th { width: 170px; }
.cat-ver { display: inline-block; padding: 2px 8px; border-radius: 999px; font-family: SFMono-Regular, Consolas, monospace; font-size: 12px; font-weight: 600; background: #EBECF0; color: #172B4D; }
.cat-beta { display: inline-block; padding: 1px 7px; border-radius: 999px; font-size: 11px; font-weight: 700; background: #FFFAE6; color: #974F0C; border: 1px solid #FFE380; }
.cat-cmd { display: inline-block; padding: 2px 8px; border-radius: 6px; font-family: SFMono-Regular, Consolas, monospace; font-size: 12px; background: #F4F5F7; border: 1px solid #DFE1E6; color: #0747A6; }
.cat-grid { display: flex; flex-wrap: wrap; gap: 12px; margin: 12px 0 20px 0; }
.cat-scen-card { flex: 1 1 calc(50% - 12px); min-width: 280px; box-sizing: border-box; background: #F9FAFC; border: 1px solid #DFE1E6; border-left: 4px solid #0052CC; border-radius: 10px; padding: 12px 16px; }
.cat-scen-title { font-weight: 600; color: #172B4D; font-size: 14px; margin-bottom: 2px; }
.cat-scen-en { color: #6B778C; font-size: 12px; margin-bottom: 8px; }
.cat-chip { display: inline-block; padding: 3px 11px; border-radius: 999px; background: #FFFFFF; border: 1px solid #C0B6F2; font-weight: 600; font-size: 12.5px; margin: 2px 6px 2px 0; box-shadow: 0 1px 2px rgba(9,30,66,0.04); }
.cat-worth-card { border-radius: 10px; padding: 12px 16px; margin: 10px 0; border: 1px solid #EBECF0; background: #FAFBFC; border-left: 4px solid #0052CC; }
.cat-worth-pain { background: #FFF8F6; border-color: #FFBDAD; border-left: 4px solid #DE350B; }
.cat-worth-without { background: #FFFAE6; border-color: #FFE380; border-left: 4px solid #FF991F; }
.cat-worth-fit { background: #F3FBF7; border-color: #ABF5D1; border-left: 4px solid #00875A; }
.cat-worth-en { background: #F4F5F7; border-color: #DFE1E6; border-left: 4px solid #5E6C84; font-size: 13px; color: #42526E; }
.cat-worth-beta { background: #FFFAE6; border-color: #FFE380; border-left: 4px solid #FF991F; }
.cat-prompt-box { background: #FFFFFF; border: 1px solid #D2D8E2; border-left: 4px solid #0052CC; border-radius: 12px; padding: 14px 18px; margin: 14px 0 20px 0; box-shadow: 0 1px 4px rgba(9,30,66,0.04); }
.cat-prompt-header { margin-bottom: 6px; font-weight: 600; font-size: 15px; color: #172B4D; }
.cat-lang-tag { display: inline-block; padding: 2px 10px; border-radius: 999px; font-size: 12px; font-weight: 600; background: #E9F2FF; color: #0747A6; border: 1px solid #B3D4FF; margin: 10px 8px 6px 0; }
.cat-lang-tag-en { background: #EBECF0; color: #253858; border-color: #C1C7D0; }
.cat-sec-h2 { border-bottom: 2px solid #E9F2FF; padding-bottom: 6px; margin-top: 26px; color: #172B4D; }
.cat-wrap .code.panel.pdl { position: relative !important; background: #F4F5F7 !important; border: 1px solid #DFE1E6 !important; border-radius: 8px !important; margin: 6px 0 14px 0 !important; box-shadow: none !important; }
.cat-wrap .codeContent.panelContent.pdl { background: #F4F5F7 !important; padding: 12px 110px 12px 16px !important; border-radius: 8px !important; }
.cat-wrap pre.syntaxhighlighter-pre, .cat-wrap .syntaxhighlighter { background: #F4F5F7 !important; color: #1F2937 !important; font-family: SFMono-Regular, Consolas, "PingFang SC", "Microsoft YaHei", monospace !important; font-size: 13px !important; line-height: 1.65 !important; margin: 0 !important; padding: 0 !important; white-space: pre-wrap !important; word-break: break-word !important; }
.cat-copy-btn { position: absolute; top: 8px; right: 10px; z-index: 5; background: #FFFFFF; color: #172B4D; border: 1px solid #C0B6F2; border-radius: 6px; padding: 4px 10px; font-size: 12px; font-weight: 600; cursor: pointer; box-shadow: 0 1px 2px rgba(9,30,66,0.06); transition: all 0.15s ease; }
.cat-copy-btn:hover { background: #E9F2FF; border-color: #0052CC; color: #0747A6; }
.cat-copy-btn.copied { background: #E3FCEF !important; color: #006644 !important; border-color: #79F2C0 !important; }
""".strip()

CONFLUENCE_COPY_JS = """
(function() {
  function copyText(text, onDone) {
    if (navigator.clipboard && window.isSecureContext) {
      navigator.clipboard.writeText(text).then(onDone).catch(function() { fallbackCopy(text, onDone); });
    } else {
      fallbackCopy(text, onDone);
    }
  }
  function fallbackCopy(text, onDone) {
    var ta = document.createElement("textarea");
    ta.value = text;
    ta.style.position = "fixed";
    ta.style.top = "-9999px";
    document.body.appendChild(ta);
    ta.focus();
    ta.select();
    try { document.execCommand("copy"); } catch (e) {}
    document.body.removeChild(ta);
    onDone();
  }
  function mountCopyButtons(root) {
    var blocks = (root || document).querySelectorAll(".cat-wrap .code.panel.pdl");
    for (var i = 0; i < blocks.length; i++) {
      var panel = blocks[i];
      if (panel.querySelector(".cat-copy-btn")) continue;
      var btn = document.createElement("button");
      btn.type = "button";
      btn.className = "cat-copy-btn";
      btn.textContent = "复制 / Copy";
      btn.addEventListener("click", (function(p, b) {
        return function() {
          var pre = p.querySelector("pre.syntaxhighlighter-pre") || p.querySelector("pre");
          var txt = pre ? pre.textContent : p.innerText;
          copyText(txt, function() {
            b.textContent = "✓ 已复制 / Copied";
            b.classList.add("copied");
            setTimeout(function() {
              b.textContent = "复制 / Copy";
              b.classList.remove("copied");
            }, 1800);
          });
        };
      })(panel, btn));
      panel.appendChild(btn);
    }
  }
  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", function() { mountCopyButtons(document); });
  } else {
    mountCopyButtons(document);
  }
  setTimeout(function() { mountCopyButtons(document); }, 300);
})();
""".strip()


def code_macro(body, language="bash"):
    """渲染一个 Confluence 代码/纯文本块（bash 用 bash 高亮，纯文字提示词用 none）。"""
    return (
        '<ac:structured-macro ac:name="code">'
        f'<ac:parameter ac:name="language">{language}</ac:parameter>'
        "<ac:plain-text-body><![CDATA["
        + body
        + "]]></ac:plain-text-body></ac:structured-macro>"
    )


def html_style_and_script():
    """渲染页面顶部的 html 宏：注入圆角多彩表格样式与代码块右上角一键复制按钮脚本。"""
    return (
        '<ac:structured-macro ac:name="html"><ac:plain-text-body><![CDATA[\n'
        f"<style>\n{CONFLUENCE_CSS}\n</style>\n"
        f"<script>\n{CONFLUENCE_COPY_JS}\n</script>\n"
        "]]></ac:plain-text-body></ac:structured-macro>"
    )


def type_badge(etype, suffix=""):
    """渲染条目类型的彩色胶囊徽章（SKILL 蓝 / MCP 紫 / TOOL 绿 / DOC 灰）。"""
    tm = TYPE_THEME.get(etype, TYPE_THEME["doc"])
    return f'<span class="cat-badge cat-badge-{escape(etype)}">{escape(tm["label"] + suffix)}</span>'


def scen_badge(text):
    """渲染场景标签的浅灰胶囊徽章。"""
    return f'<span class="cat-badge cat-badge-scen">{escape(text)}</span>'


def entry_page_link(entry, config, text=None):
    """渲染指向条目 Confluence 子页的内部链接（点击直接跳对应子页）。"""
    space_key = config["confluence"]["space_key"]
    title = f"{entry['name']} — {entry['meta']['title_zh']}"
    label = text or entry["name"]
    return (
        f'<ac:link><ri:page ri:space-key="{escape(space_key)}" ri:content-title="{escape(title)}" />'
        f"<ac:plain-text-link-body><![CDATA[{label}]]></ac:plain-text-link-body></ac:link>"
    )


def render_worth_section(entry):
    """把「为什么值得装」一节渲染成带左侧语义色条的圆角卡片块；条目没有该节则返回空串。

    支持：`- ` 开头的列表项（含多行续行）与普通段落，按「解决什么痛点 / 不装会怎样 / 适合谁 / English」
    自动匹配左侧色条与柔和底色。
    """
    lines = readme_worth_section(entry["meta_path"])
    if not lines:
        return ""
    parts = ['<h2 class="cat-sec-h2">为什么值得装 / Why it&#39;s worth it</h2>']
    if is_prerelease((entry.get("meta") or {}).get("version")):
        parts.append(
            '<div class="cat-worth-card cat-worth-beta"><p style="margin:0;">'
            "<strong>0.x 测试版</strong> —— 尚未经过严格测试；行为可能变化，请先在非关键流程试用。"
            "</p></div>"
        )
    buf = []

    def emit_card(text):
        """按段落关键词选择对应色条样式并输出卡片。"""
        html_txt = inline(text)
        if "解决什么痛点" in text:
            cls = "cat-worth-card cat-worth-pain"
        elif "不装会怎样" in text:
            cls = "cat-worth-card cat-worth-without"
        elif "适合谁" in text:
            cls = "cat-worth-card cat-worth-fit"
        elif text.startswith("**English") or "English." in text or "诚实说明" in text:
            cls = "cat-worth-card cat-worth-en"
        else:
            cls = "cat-worth-card"
        parts.append(f'<div class="{cls}"><p style="margin:0;">{html_txt}</p></div>')

    def flush_buf():
        """把当前累积的行合并成一个卡片输出。"""
        if buf:
            emit_card(" ".join(buf))
            buf.clear()

    for line in lines:
        stripped = line.strip()
        if not stripped:
            flush_buf()
        elif stripped.startswith("- "):
            flush_buf()
            buf.append(stripped[2:])
        else:
            buf.append(stripped)
    flush_buf()
    return "".join(parts)


def beta_render_selftest():
    """0.x beta 徽章与首条的自测：0.x 必须有，1.x 必须没有。"""
    errors = []
    with tempfile.TemporaryDirectory() as tmp:
        readme = Path(tmp) / "README.md"
        readme.write_text(
            "## 为什么值得装 / Why it's worth it\n\n- **解决什么痛点** —— x\n",
            encoding="utf-8",
        )
        for version, expected in (("0.2.0", True), ("1.0.0", False)):
            entry = {"meta_path": readme, "meta": {"version": version}}
            if ("0.x 测试版" in render_worth_section(entry)) != expected:
                errors.append(
                    f"beta_render 自测失败：version={version} 的首条 beta 卡片预期 {expected}"
                )
            if ("beta" in version_badge(version)) != expected:
                errors.append(
                    f"beta_render 自测失败：version={version} 的版本徽章预期 beta={expected}"
                )
            if ("beta" in version_text(version)) != expected:
                errors.append(
                    f"beta_render 自测失败：version={version} 的目录表版本预期 beta={expected}"
                )
    return errors


def body_hash(body):
    """正文的短哈希，用于判断页面是否落后于仓库。"""
    return hashlib.sha1(body.encode("utf-8")).hexdigest()[:16]


def render_group_table(rows, config, etype=None):
    """渲染一个 type 分组的条目索引表（总览页与类别页共用，按类型赋予专属表头配色）。"""
    extra_cls = f" cat-table-{etype}" if etype else ""
    parts = [
        f'<table class="cat-table{extra_cls}"><tbody>',
        "<tr><th>条目 / Entry</th><th>版本</th><th>一句话简介 / Summary</th><th>怎么调用 / Entry</th><th>源码位置</th><th>维护者</th></tr>",
    ]
    for entry in rows:
        meta = entry["meta"]
        parts.append(
            f"<tr><td><strong>{entry_page_link(entry, config)}</strong></td>"
            f'<td>{version_badge(meta["version"])}</td>'
            f"<td>{inline(meta['summary_zh'])}</td>"
            f'<td><span class="cat-cmd">{escape(meta["entry"])}</span></td>'
            f'<td><a href="{config["repo_browse_url"]}/{entry["path"]}">{escape(entry["path"])}/</a></td>'
            f"<td>{maintainer_html(meta)}</td></tr>"
        )
    parts.append("</tbody></table>")
    return "".join(parts)


def render_index_table(entries, config):
    """渲染总览页的条目索引表（按 type 分组，带类型胶囊与一句话说明）。"""
    parts = []
    for group in ("skill", "mcp", "tool", "doc"):
        rows = [e for e in entries if e["dir_type"] == group]
        if not rows:
            continue
        zh_intro, _ = CATEGORY_INTRO.get(group, ("", ""))
        parts.append(
            f"<h3>{type_badge(group)} "
            f'<span style="font-size:14px; color:#5E6C84; font-weight:normal; margin-left:6px;">{escape(zh_intro)}</span></h3>'
        )
        parts.append(render_group_table(rows, config, etype=group))
    return "".join(parts)


def render_category_page(etype, rows, config):
    """渲染一个类别页（SKILL / MCP / …）的 storage 正文：顶部导语横幅 + 该类条目的圆角索引表。"""
    zh, en = CATEGORY_INTRO.get(etype, (f"{etype} 类条目。", f"{etype} items."))
    tm = TYPE_THEME.get(etype, TYPE_THEME["doc"])
    return "".join(
        [
            html_style_and_script(),
            '<div class="cat-wrap">',
            f'<div class="cat-hero" style="border-left-color: {tm["color"]};">',
            f'<div class="cat-hero-title">{type_badge(etype)} &nbsp;{inline(zh)}</div>',
            f'<div class="cat-hero-sub"><em>{inline(en)}</em>（当前共 <strong>{len(rows)}</strong> 个条目）</div>',
            "</div>",
            render_group_table(rows, config, etype=etype),
            "</div>",
        ]
    )


def render_scenario_section(entries, config):
    """渲染总览页的「按场景导航」双列圆角卡片网格（由 scenario 字段聚合，胶囊直达子页）。"""
    parts = ['<h2 class="cat-sec-h2">按场景导航 / Find it by task</h2><div class="cat-grid">']
    for sid, (zh, en) in SCENARIOS.items():
        hits = [e for e in entries if sid in (e["meta"].get("scenario") or [])]
        if not hits:
            continue
        chips = "".join(f'<span class="cat-chip">{entry_page_link(e, config)}</span>' for e in hits)
        parts.append(
            f'<div class="cat-scen-card">'
            f'<div class="cat-scen-title">{escape(zh)}</div>'
            f'<div class="cat-scen-en">{escape(en)}</div>'
            f"<div>{chips}</div>"
            f"</div>"
        )
    parts.append("</div>")
    return "".join(parts)


def render_overview(entries, config):
    """渲染总览页的 storage 正文（方案 A3：多彩语义混搭）。"""
    counts = {}
    for e in entries:
        counts[e["dir_type"]] = counts.get(e["dir_type"], 0) + 1
    pills = [f'<span class="cat-pill">共 {len(entries)} 个条目</span>']
    for group in ("skill", "mcp", "tool", "doc"):
        if counts.get(group):
            pills.append(type_badge(group, f" × {counts[group]}"))

    return "".join(
        [
            html_style_and_script(),
            '<div class="cat-wrap">',
            '<div class="cat-hero">',
            '<div class="cat-hero-title">ANSC_CAS AI Toolbox</div>',
            f'<p style="margin:4px 0;">ai-toolbox 是一个 AI 工具箱仓库，目前有 <strong>{len(entries)}</strong> 个条目'
            "（skill / MCP / tool）。条目按类型分目录，每个条目<strong>自包含、带版本、可一键安装</strong>，也可整份拷走或整份删掉。</p>",
            '<div class="cat-pills">' + " ".join(pills) + "</div>",
            "</div>",
            '<ac:structured-macro ac:name="info"><ac:parameter ac:name="title">本页由仓库自动生成（唯一真源：ai-toolbox 仓库）</ac:parameter><ac:rich-text-body>'
            "<p><strong>请勿在 Confluence 上直接手工编辑。</strong>"
            "改动请提 change 到 Gerrit（见下方「怎么贡献」），跑 <code>./scripts/catalog.py sync --apply</code> 自动同步（也可以直接对 AI 说「发布到 Confluence」）；页面会被下次发布覆盖。</p>"
            "</ac:rich-text-body></ac:structured-macro>",
            '<h2 class="cat-sec-h2">条目索引 / Catalog Index</h2>',
            '<p style="color:#5E6C84;">点击<strong>条目名</strong>可直接进入对应的 Confluence 详情子页（含一键安装与 AI 代装提示词）；点击<strong>源码位置</strong>可前往 GitLab 查看源码。表里的「维护者」指<strong>本仓该条目的负责人</strong>，不是上游作者。</p>',
            render_index_table(entries, config),
            render_scenario_section(entries, config),
            '<h2 class="cat-sec-h2">怎么贡献 / Contributing</h2>',
            "<p>改动这个仓库需要两个账号：</p>",
            "<ul>"
            "<li><strong>GitLab 账号</strong>（<code>172.21.1.202</code>）："
            "克隆仓库、看代码、对照 <code>skills/_template/</code> 条目模板。</li>"
            "<li><strong>Gerrit 账号 + push 权限</strong>（<code>172.21.1.201</code>）："
            "所有改动都走 Gerrit 评审，提交用 <code>git review</code>（或本仓的 <code>/auto-commit</code>）。</li>"
            "</ul>",
            "<p>克隆仓库后，按 <code>README.md</code> 等文档进行新的 SKILL、MCP、AI 工具的开发。</p>",
            '<h2 class="cat-sec-h2">许可与合规 / License &amp; Compliance</h2>',
            '<ac:structured-macro ac:name="note"><ac:parameter ac:name="title">合规提醒：gitnexus 上游为非商业许可</ac:parameter><ac:rich-text-body>'
            "<p>各条目的上游与许可写在条目自己的元数据与 README 里。"
            "注意 <strong>gitnexus 的上游是 PolyForm Noncommercial 1.0.0（非商业许可）</strong>，"
            "公司内部使用前请自行确认合规；若需 MIT 许可替代方案可使用 <strong>codegraph</strong>。</p>"
            "</ac:rich-text-body></ac:structured-macro>",
            '<h2 class="cat-sec-h2">本页怎么更新 / How this page is updated</h2>',
            "<p>由 <code>scripts/catalog.py publish</code> 从仓库生成。"
            "仓库是唯一真源，本页是只读产物。</p>",
            "</div>",
        ]
    )


def render_entry_page(entry, config):
    """渲染单个条目的子页 storage 正文（带类型专属色条、圆角属性表、色条痛点块与一键复制提示词）。"""
    meta = entry["meta"]
    etype = entry["dir_type"]
    tm = TYPE_THEME.get(etype, TYPE_THEME["doc"])
    browse = f"{config['repo_browse_url']}/{entry['path']}"
    deps_html = (
        " ".join(f'<span class="cat-cmd">{escape(d)}</span>' for d in meta["deps"])
        or '<span style="color:#6B778C;">无（零外部依赖）</span>'
    )
    scen_badges = " ".join(
        scen_badge(SCENARIOS[s][0]) for s in (meta.get("scenario") or []) if s in SCENARIOS
    )
    rows = [
        ("类型 / Type", f"{type_badge(etype)} &nbsp;{scen_badges}"),
        ("版本 / Version", version_badge(meta["version"])),
        ("怎么调用 / Entry", f'<span class="cat-cmd">{escape(meta["entry"])}</span>'),
        ("依赖 / Dependencies", deps_html),
        ("上游 / Upstream", escape(meta["upstream"])),
        ("位置 / Location", f'<a href="{browse}"><code>{escape(entry["path"])}/</code></a>'),
        ("维护者 / Maintainer", maintainer_html(meta)),
    ]
    table = (
        f'<table class="cat-table cat-kv-table cat-table-{escape(etype)}"><tbody>'
        + "".join(f"<tr><th>{k}</th><td>{v}</td></tr>" for k, v in rows)
        + "</tbody></table>"
    )

    if meta["install"] == "none":
        install = (
            '<ac:structured-macro ac:name="tip"><ac:parameter ac:name="title">开箱即用（无需安装）</ac:parameter><ac:rich-text-body>'
            "<p>无需安装：本条目就在本仓的 <code>.devin/skills/</code> 下，克隆本仓即生效"
            "（仅在本仓内可用；要用到自己的项目，请把该目录整份拷走）。</p>"
            "</ac:rich-text-body></ac:structured-macro>"
        )
    else:
        # 「怎么装」的代码块以 README 的「一键安装」段为准（真源）；只有提取不到时才回退
        block = readme_install_block(entry["meta_path"])
        if block is None:
            block = (
                f"git clone {config['repo_url']} ai-toolbox\n"
                f"cd ai-toolbox/{entry['path']}\n"
                f"{meta['install']}"
            )
        install = code_macro(block, language="bash")

    prompts = readme_ai_prompts(entry["meta_path"])
    ai_section = ""
    if prompts:
        parts = [
            f'<div class="cat-prompt-box" style="border-left-color: {tm["color"]};">',
            '<div class="cat-prompt-header">不想手动敲命令？让 AI 代劳 / Let your AI agent do it</div>',
            '<p style="margin:0 0 6px 0; color:#42526E; font-size:13px;">点右上角「复制 / Copy」按钮，把下面这段整段粘给你的 AI Agent（Devin Desktop / Devin CLI），'
            "它会自己装、自己验证：</p>",
            '<div><span class="cat-lang-tag">中文提示词（点右上角一键复制）</span></div>',
            code_macro(prompts[0], language="none"),
        ]
        if len(prompts) > 1:
            parts += [
                '<div><span class="cat-lang-tag cat-lang-tag-en">English Prompt (Click Copy)</span></div>',
                code_macro(prompts[1], language="none"),
            ]
        parts.append("</div>")
        ai_section = "".join(parts)

    # 「怎么升级」：装完才会用到的第二件事 —— 重跑安装即升级，先查有没有新版
    upgrade_section = ""
    if meta["install"] != "none":
        upgrade_block = readme_upgrade_block(entry["meta_path"])
        upgrade_prompts = readme_upgrade_prompts(entry["meta_path"])
        if upgrade_block or upgrade_prompts:
            parts = ['<h2 class="cat-sec-h2">怎么升级 / Upgrade</h2>']
            if upgrade_block:
                parts += [
                    "<p>安装脚本是幂等的：<strong>重跑就是升级</strong>（载荷整份覆盖，"
                    "本地手改会被冲掉）。先查有没有新版，再决定要不要升。</p>",
                    code_macro(upgrade_block, language="bash"),
                ]
            if upgrade_prompts:
                parts += [
                    f'<div class="cat-prompt-box" style="border-left-color: {tm["color"]};">',
                    '<div class="cat-prompt-header">让 AI 查更新 / 升级 · Let your AI agent check &amp; upgrade</div>',
                    '<p style="margin:0 0 6px 0; color:#42526E; font-size:13px;">点右上角「复制 / Copy」把下面这段整段粘给你的 AI Agent —— 它会先查、再问你要不要升级：</p>',
                    '<div><span class="cat-lang-tag">中文提示词（查更新/升级）</span></div>',
                    code_macro(upgrade_prompts[0], language="none"),
                ]
                if len(upgrade_prompts) > 1:
                    parts += [
                        '<div><span class="cat-lang-tag cat-lang-tag-en">English Prompt (Check &amp; Upgrade)</span></div>',
                        code_macro(upgrade_prompts[1], language="none"),
                    ]
                parts.append("</div>")
            upgrade_section = "".join(parts)

    return "".join(
        [
            html_style_and_script(),
            '<div class="cat-wrap">',
            f'<div class="cat-hero" style="border-left-color: {tm["color"]};">',
            f'<div class="cat-hero-title">{type_badge(etype)} {version_badge(meta["version"])} '
            f'<span>{escape(entry["name"])} — {escape(meta["title_zh"])}</span></div>',
            f'<p style="margin:6px 0 4px 0; font-size:14.5px;">{inline(meta["summary_zh"])}</p>',
            f'<div class="cat-hero-sub"><em>{inline(meta["summary_en"])}</em></div>',
            "</div>",
            table,
            render_worth_section(entry),
            '<h2 class="cat-sec-h2">怎么装 / Install</h2>',
            install,
            ai_section,
            upgrade_section,
            '<h2 class="cat-sec-h2">完整文档 / Full docs</h2>',
            f'<p>见仓库里的 <a href="{browse}"><strong>{escape(entry["path"])}/</strong></a>。</p>',
            "</div>",
        ]
    )


def build_payload(entries, config):
    """组装 Confluence 页面树 payload（总览页 → 类别页 → 条目页，三层）。"""
    pages = [
        {"key": key, "title": title, "parent": parent, "body": body}
        for key, title, body, parent in expected_pages(entries, config)
    ]
    children = {}
    for page in pages:
        children.setdefault(page["parent"], []).append(page["key"])
    for page in pages:
        page["children"] = children.get(page["key"], [])
    return {
        "space_key": config["confluence"]["space_key"],
        "overview_page": "空间首页（publish 时解析 / resolved by publish）",
        "pages": pages,
    }


def fail(code, message):
    """打印一行失败信息并退出。"""
    print(f"[FAIL] {message}", file=sys.stderr)
    sys.exit(code)


def next_version(current, kind):
    """按 kind（major / minor / patch）把 semver 升一级，返回新版本号。"""
    major, minor, patch = (int(part) for part in current.split("."))
    if kind == "major":
        return f"{major + 1}.0.0"
    if kind == "minor":
        return f"{major}.{minor + 1}.0"
    return f"{major}.{minor}.{patch + 1}"


def bump_entry(entry, kind):
    """就地改写条目文档 front-matter 里的 version，返回 (旧版本, 新版本)。"""
    text = entry["meta_path"].read_text(encoding="utf-8")
    match = FRONT_MATTER_RE.match(text)
    if not match:
        fail(1, f"{entry['path']}: 缺少 front-matter，先补一个再 bump")

    block = match.group(1)
    line = VERSION_LINE_RE.search(block)
    if not line:
        fail(1, f"{entry['path']}: front-matter 里没有 `version:` 字段")
    current = line.group(1).strip().strip('"').strip("'")
    if not SEMVER_RE.match(current):
        fail(1, f"{entry['path']}: `version` 是 `{current}`，不是严格 semver（x.y.z），先手工改对再 bump")

    new = next_version(current, kind)
    new_block = block[: line.start()] + f"version: {new}" + block[line.end() :]
    entry["meta_path"].write_text(
        text[: match.start(1)] + new_block + text[match.end(1) :], encoding="utf-8"
    )
    return current, new


def cmd_bump(args):
    """bump：给某个条目升一级版本号，直接改写它的 front-matter（写盘）。"""
    entries = {entry["name"]: entry for entry in collect_entries()}
    entry = entries.get(args.name)
    if entry is None:
        fail(2, f"没有这个条目 / no such entry: {args.name}（现有：{', '.join(sorted(entries))}）")
    if entry["meta"] is None:
        fail(1, f"{entry['path']}: 缺少 front-matter")

    old, new = bump_entry(entry, args.kind)
    print(f"[BUMP] {entry['name']}: {old} → {new}（{entry['meta_file']}）")
    print("[INFO] 接着跑 ./scripts/catalog.py sync --apply，把新版本号带到 README 与 Confluence")
    return 0


def cmd_check(args):
    """check：校验仓库侧的元数据与 README 目录表；--remote 时额外比对 Confluence。只读。"""
    entries = collect_entries()
    if not entries:
        fail(1, "没有扫描到任何条目 / no entries found")

    errors = validate(entries)

    readme_text = README_PATH.read_text(encoding="utf-8")
    try:
        if replace_readme_table(readme_text, render_readme_table(entries)) != readme_text:
            errors.append(
                "README.md: 目录表与元数据不一致 —— 跑 ./scripts/catalog.py build --apply 重写"
            )
    except ValueError as exc:
        errors.append(f"README.md: {exc}")

    if errors:
        for err in errors:
            print(f"[ERR]  {err}", file=sys.stderr)
        print(f"\n[FAIL] {len(errors)} 处问题 / {len(errors)} problem(s)", file=sys.stderr)
        sys.exit(1)
    print(f"[OK]   {len(entries)} 个条目的元数据与 README 目录表一致 / {len(entries)} entries valid")

    if not args.remote:
        return 0

    config = load_config()
    try:
        rows = remote_drift(entries, config)
    except ConfluenceError as exc:
        fail(2, f"Confluence 调用失败 / request failed: {exc}\n  检查凭据: {CONFLUENCE_CONFIG}")

    bad = 0
    for state, title, note in rows:
        if state != "OK":
            bad += 1
        print(f"[{state:9}] {title} —— {note}")
    if bad:
        print(f"\n[FAIL] Confluence 上有 {bad} 页与仓库不一致 / {bad} page(s) out of sync", file=sys.stderr)
        sys.exit(1)
    print(f"[OK]   Confluence 上 {len(rows)} 页与仓库一致 / {len(rows)} pages in sync")
    return 0


def cmd_build(args):
    """build：渲染 README 目录表与 Confluence payload；默认 dry-run，--apply 才落盘。"""
    entries = collect_entries()
    errors = validate(entries)
    if errors:
        for err in errors:
            print(f"[ERR]  {err}", file=sys.stderr)
        fail(1, "元数据有错，先跑 check 修好再 build")

    config = load_config()
    table = render_readme_table(entries)
    payload = build_payload(entries, config)

    try:
        new_readme = replace_readme_table(README_PATH.read_text(encoding="utf-8"), table)
    except ValueError as exc:
        fail(1, str(exc))

    changes = maintainer_line_changes(entries)
    dirty = sum(1 for _, _, changed in changes if changed)

    if not args.apply:
        print("[INFO] dry-run（未写入）。加 --apply 实际落盘 / dry-run, pass --apply to write")
        print(f"[INFO] README 目录表将写入 {len(entries)} 行：")
        for line in table.splitlines():
            print(f"       {line}")
        print(f"[INFO] 条目 README 的维护者行将更新 {dirty} 个文件")
        print(f"[INFO] Confluence payload 将写入 {PAYLOAD_DIR.relative_to(REPO_ROOT)}/（{len(payload['pages'])} 页）")
        return 0

    README_PATH.write_text(new_readme, encoding="utf-8")
    print(f"[SYNC] README 目录表已更新（{len(entries)} 行）/ README table updated")

    for path, new_text, changed in changes:
        if changed:
            path.write_text(new_text, encoding="utf-8")
    print(f"[SYNC] 条目 README 的维护者行已更新（{dirty} 个文件）/ maintainer lines updated")

    PAYLOAD_DIR.mkdir(parents=True, exist_ok=True)
    (PAYLOAD_DIR / "pages.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(f"[SYNC] payload 已写入 / payload written: {PAYLOAD_DIR.relative_to(REPO_ROOT)}/pages.json")
    return 0


class ConfluenceError(Exception):
    """Confluence REST 调用失败。"""


_CLIENT = {}


def confluence_client():
    """惰性建立 Confluence 客户端：base、请求头与 requests 模块。"""
    if not _CLIENT:
        try:
            import requests
            import urllib3
        except ImportError:
            fail(
                2,
                "缺少依赖 / missing dependency: requests\n"
                '  检查: python3 -c "import requests; print(requests.__version__)"\n'
                "  安装: pip3 install requests",
            )
        urllib3.disable_warnings()
        if not CONFLUENCE_CONFIG.is_file():
            fail(
                2,
                f"缺少凭据文件 / missing credentials: {CONFLUENCE_CONFIG}\n"
                "  怎么办: 申请一个 Confluence PAT 写进该文件，"
                "或用 CATALOG_CONFLUENCE_CONFIG 指向别处",
            )
        cfg = json.loads(CONFLUENCE_CONFIG.read_text(encoding="utf-8"))
        base = (cfg.get("confluence_url") or "").rstrip("/")
        token = cfg.get("confluence_token") or ""
        if not base or not token or token.startswith("<"):
            fail(2, f"{CONFLUENCE_CONFIG} 里的 confluence_url / confluence_token 没填好")
        _CLIENT.update(
            base=base,
            requests=requests,
            headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
        )
    return _CLIENT


def confluence(method, path, payload=None, params=None):
    """调用 Confluence REST API，返回解析后的 JSON；非 2xx 抛 ConfluenceError。"""
    client = confluence_client()
    resp = client["requests"].request(
        method,
        client["base"] + path,
        headers=client["headers"],
        json=payload,
        params=params,
        verify=False,
        timeout=60,
    )
    if resp.status_code >= 400:
        raise ConfluenceError(f"{method} {path} -> HTTP {resp.status_code}: {resp.text[:300]}")
    return resp.json()


def space_homepage_id(space_key):
    """取空间首页的 page id —— 总览页复用它。"""
    data = confluence("GET", f"/rest/api/space/{space_key}", params={"expand": "homepage"})
    home = data.get("homepage") or {}
    if not home.get("id"):
        raise ConfluenceError(f"空间 {space_key} 没有首页 / no homepage")
    return home["id"]


def list_children(page_id, expand="version"):
    """列出某页的直接子页（分页取全）。"""
    out, start = [], 0
    while True:
        data = confluence(
            "GET",
            f"/rest/api/content/{page_id}/child/page",
            params={"limit": 100, "start": start, "expand": expand},
        )
        out += data.get("results", [])
        if not data.get("results") or len(out) >= data.get("size", 0):
            return out
        start += len(data["results"])


def page_labels(page_id):
    """取页面的标签名集合。"""
    data = confluence("GET", f"/rest/api/content/{page_id}/label")
    return {label.get("name") for label in data.get("results", [])}


def page_storage(page_id):
    """取页面的 storage 正文。"""
    data = confluence("GET", f"/rest/api/content/{page_id}", params={"expand": "body.storage"})
    return ((data.get("body") or {}).get("storage") or {}).get("value", "")


def ensure_label(page_id, label=CONFLUENCE_LABEL):
    """给页面打上 catalog 标签（幂等）—— 孤儿检测靠它认出「哪些页是本脚本建的」。"""
    if label in page_labels(page_id):
        return
    confluence("POST", f"/rest/api/content/{page_id}/label", payload=[{"prefix": "global", "name": label}])


def get_page_property(page_id, key=PROPERTY_KEY):
    """读页面的内容属性；不存在（404）返回 None，其他错误照抛。"""
    try:
        return confluence("GET", f"/rest/api/content/{page_id}/property/{key}").get("value")
    except ConfluenceError as exc:
        if "HTTP 404" in str(exc):
            return None
        raise


def set_page_property(page_id, value, key=PROPERTY_KEY):
    """写页面的内容属性（幂等：已存在则递增版本更新）。"""
    if get_page_property(page_id, key) is None:
        confluence("POST", f"/rest/api/content/{page_id}/property", payload={"key": key, "value": value})
        return
    raw = confluence("GET", f"/rest/api/content/{page_id}/property/{key}")
    number = ((raw.get("version") or {}).get("number", 0)) + 1
    confluence(
        "PUT",
        f"/rest/api/content/{page_id}/property/{key}",
        payload={"key": key, "value": value, "version": {"number": number}},
    )


def record_publish_state(page_id, intended_body):
    """记录这次发布的正文哈希：仓库侧的哈希 + Confluence 回读后的规范化正文哈希。

    回读的哈希是「页面被人手工编辑过」的判据 —— 只要正文再被人改一次，
    回读哈希就对不上记录值。
    """
    set_page_property(
        page_id,
        {
            "repo_hash": body_hash(intended_body),
            "body_hash": body_hash(page_storage(page_id)),
            "published": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        },
    )


def expected_pages(entries, config):
    """返回 [(key, 标题, storage 正文, 父页标题)]：总览页 + 类别页 + 条目页，三层。

    父页标题：总览页是空间首页本身（None）；类别页挂在总览页下（"__overview__"）；
    条目页挂在所属类别页下。类别 = `type` 字段，类别页标题 = type 大写；
    某 type 有条目才有它的类别页，新 type 出现时类别页自动出现。
    """
    pages = [
        (
            "__overview__",
            config["confluence"]["overview_title"],
            render_overview(entries, config),
            None,
        )
    ]
    for etype in TYPE_ORDER:
        rows = [e for e in entries if e["dir_type"] == etype]
        if not rows:
            continue
        pages.append(
            (f"cat:{etype}", etype.upper(), render_category_page(etype, rows, config), "__overview__")
        )
    pages += [
        (
            entry["name"],
            f"{entry['name']} — {entry['meta']['title_zh']}",
            render_entry_page(entry, config),
            entry["dir_type"].upper(),
        )
        for entry in entries
    ]
    return pages


def is_up_to_date(current, body):
    """这一页是否已经是仓库的最新内容（且没被人手改过）。"""
    if current is None:
        return False
    state = get_page_property(current["id"])
    stored = ((current.get("body") or {}).get("storage") or {}).get("value", "")
    return bool(
        state
        and state.get("repo_hash") == body_hash(body)
        and state.get("body_hash") == body_hash(stored)
    )


def build_publish_plan(entries, config):
    """比对仓库与 Confluence，返回 (home_id, actions)。只读，不写任何东西。

    页面树三层：首页 → 类别页 → 条目页。动作 kind：
    overview / create / update / skip / move / order / orphan ——
    skip = 内容最新且挂对了地方（否则 `sync --apply` 每跑一次都会把版本号 +1，
    产生一堆无意义的新版本）；move = 内容不用改但父页不对（如被手工拖动），
    挪回正确类别页；order = 子页顺序不对，apply 时提示手工拖动（本仓部署的
    Confluence Server 没有 Cloud 的 move API）；orphan =
    仓库里已删除的条目页，打「已从仓库移除」横幅。
    """
    space = config["confluence"]["space_key"]
    home_id = space_homepage_id(space)
    home = confluence(
        "GET", f"/rest/api/content/{home_id}", params={"expand": "version,body.storage"}
    )
    home_children = {
        child["title"]: child for child in list_children(home_id, expand="version,body.storage")
    }

    pages = expected_pages(entries, config)
    cat_ordered = [title for _, title, _, parent in pages if parent == "__overview__"]
    cat_titles = set(cat_ordered)
    cat_pages = {title: home_children.get(title) for title in cat_ordered}

    # 条目页可能出现的位置：正确类别页下 / 首页下（旧结构或被拖错）/ 其他类别页下
    locations = {}  # 标题 → [(page, 父页标题；None = 挂在首页下)]
    for title, child in home_children.items():
        if title not in cat_titles:
            locations.setdefault(title, []).append((child, None))
    cat_children = {}  # 类别标题 → 其子页列表（远端顺序）
    for title in cat_ordered:
        cat_page = cat_pages[title]
        if cat_page is None:
            continue
        children = list_children(cat_page["id"], expand="version,body.storage")
        cat_children[title] = children
        for child in children:
            locations.setdefault(child["title"], []).append((child, title))

    actions, expected_titles = [], set()
    for key, title, body, parent in pages:
        expected_titles.add(title)
        if parent is None:  # 总览页：它就是首页
            current, parent_ok = home, True
        elif parent == "__overview__":  # 类别页：应挂在首页下
            current = cat_pages[title]
            parent_ok = current is not None
        else:  # 条目页：应挂在所属类别页下
            found = locations.get(title) or []
            correct = [page for page, pt in found if pt == parent]
            current = correct[0] if correct else (found[0][0] if found else None)
            parent_ok = bool(correct)

        if current is None:
            kind = "create"
        elif not parent_ok:
            kind = "move"
        elif is_up_to_date(current, body):
            kind = "skip"
        elif key == "__overview__":
            kind = "overview"
        else:
            kind = "update"
        actions.append(
            {
                "kind": kind,
                "key": key,
                "title": title,
                "parent": parent,
                "page_id": (current or {}).get("id"),
                "version": ((current or {}).get("version") or {}).get("number", 0),
                "body": body,
            }
        )

    for title, child in home_children.items():
        if title in expected_titles or CONFLUENCE_LABEL not in page_labels(child["id"]):
            continue
        actions.append(
            {
                "kind": "orphan",
                "key": title,
                "title": title,
                "parent": "__overview__",
                "page_id": child["id"],
                "version": (child.get("version") or {}).get("number", 0),
                "body": None,
            }
        )
    for title, children in cat_children.items():
        for child in children:
            if child["title"] in expected_titles or CONFLUENCE_LABEL not in page_labels(child["id"]):
                continue
            actions.append(
                {
                    "kind": "orphan",
                    "key": child["title"],
                    "title": child["title"],
                    "parent": title,
                    "page_id": child["id"],
                    "version": (child.get("version") or {}).get("number", 0),
                    "body": None,
                }
            )

    # 顺序计划：类别页按 TYPE_ORDER（SKILL → MCP → …），类别内条目按标题字母序；
    # 顺序已经对就不发动作（apply 时 check_order 还会按远端现状再核对一次）
    current_cat_order = [t for t in home_children if t in cat_titles]
    if current_cat_order != cat_ordered:
        actions.append(
            {
                "kind": "order",
                "key": "__overview__",
                "title": config["confluence"]["overview_title"],
                "parent": None,
                "page_id": home_id,
                "version": 0,
                "body": None,
                "desired": cat_ordered,
            }
        )
    for title in cat_ordered:
        cat_page = cat_pages[title]
        if cat_page is None:
            continue
        desired = sorted(t for _, t, _, parent in pages if parent == title)
        current_order = [c["title"] for c in cat_children.get(title, []) if c["title"] in desired]
        if current_order != desired:
            actions.append(
                {
                    "kind": "order",
                    "key": title,
                    "title": title,
                    "parent": "__overview__",
                    "page_id": cat_page["id"],
                    "version": 0,
                    "body": None,
                    "desired": desired,
                }
            )
    return home_id, actions


def check_order(parent_id, desired_titles, label):
    """检查 parent 页的子页顺序是否等于 desired_titles，返回不一致的父页数。

    本仓部署的 Confluence 是 Server/DC，没有 Cloud 的
    `PUT /rest/api/content/{id}/move/{position}/{targetId}` 端点（调用会 404），
    所以这里只检测、不自动移动，提示人工在页面树里拖动。读取失败是尽力而为的：
    打一行警告后返回 0，绝不让一次临时读失败把已经写完的发布变成退出码 3。
    """
    try:
        children = list_children(parent_id)
    except ConfluenceError as exc:
        print(
            f"[WARN] {label}顺序检查失败，可手工在页面树里拖动: {exc}",
            file=sys.stderr,
        )
        return 0
    current = [child["title"] for child in children if child["title"] in desired_titles]
    if current == list(desired_titles):
        return 0
    print(
        f"[INFO] {label}顺序与期望不一致，请在 Confluence 页面树里手工拖动"
        f"（当前 {current}，期望 {list(desired_titles)}）"
    )
    return 1


def check_order_selftest():
    """check_order 的自测：stub list_children，三种路径都不碰网络。

    顺序一致 → 0 且无输出；顺序不一致 → 1 且恰好一行 [INFO]；
    读取抛 ConfluenceError → 0 且恰好一行 [WARN]（尽力而为，不让发布失败）。
    """
    errors = []
    real = globals()["list_children"]

    def children(_page_id, expand="version"):
        """固定子页列表：标题与顺序都可预期。"""
        return [
            {"title": title, "id": str(index)}
            for index, title in enumerate(("SKILL", "MCP", "TOOL"))
        ]

    def broken(_page_id, expand="version"):
        """模拟 list_children 读取失败。"""
        raise ConfluenceError("GET /rest/api/content/1/child/page -> HTTP 500")

    cases = (
        ("match", children, ["SKILL", "MCP", "TOOL"], 0, None),
        ("mismatch", children, ["TOOL", "MCP", "SKILL"], 1, "[INFO]"),
        ("read-failure", broken, ["SKILL", "MCP", "TOOL"], 0, "[WARN]"),
    )
    for label, stub, desired, expected, marker in cases:
        buf = io.StringIO()
        globals()["list_children"] = stub
        try:
            with contextlib.redirect_stdout(buf), contextlib.redirect_stderr(buf):
                got = check_order(1, desired, "selftest ")
        finally:
            globals()["list_children"] = real
        output = buf.getvalue()
        if got != expected:
            errors.append(f"check_order 自测失败：{label} 预期返回 {expected}，实际 {got}")
        if marker is None:
            if output:
                errors.append(f"check_order 自测失败：{label} 不应有输出，实际 {output!r}")
        elif output.count(marker) != 1:
            errors.append(
                f"check_order 自测失败：{label} 预期恰好一行 {marker}，实际 {output!r}"
            )
    return errors


def apply_publish(config, home_id, actions):
    """执行发布计划，返回 (更新, 新建, 挪回, 顺序待手工拖动, 标记孤儿, 跳过) 六个计数。"""
    space = config["confluence"]["space_key"]
    updated = created = moved = out_of_order = orphaned = skipped = 0
    parent_ids = {}  # 类别页标题 → page id；条目页挂靠时查这里
    for act in actions:
        if act["parent"] == "__overview__" and act["page_id"]:
            parent_ids[act["title"]] = act["page_id"]
        kind = act["kind"]
        if kind == "skip":
            skipped += 1
            continue
        if kind == "order":
            out_of_order += check_order(act["page_id"], act["desired"], f"{act['title']} 的子页")
            continue
        if kind == "orphan":
            stored = page_storage(act["page_id"])
            if ORPHAN_BANNER in stored:
                continue
            banner = (
                '<ac:structured-macro ac:name="warning"><ac:rich-text-body>'
                f"<p><strong>{ORPHAN_BANNER}</strong> —— 仓库里已经没有这个条目，本页不再更新。"
                "确认无用后请手工删除。</p></ac:rich-text-body></ac:structured-macro>"
            )
            confluence(
                "PUT",
                f"/rest/api/content/{act['page_id']}",
                payload={
                    "id": act["page_id"],
                    "type": "page",
                    "title": act["title"],
                    "space": {"key": space},
                    "body": {"storage": {"value": banner + stored, "representation": "storage"}},
                    "version": {"number": act["version"] + 1, "message": "catalog: 标记为孤儿条目"},
                },
            )
            orphaned += 1
            continue

        if act["parent"] in ("__overview__", None):  # 总览页就是空间首页本身（parent=None）
            parent_id = home_id
        else:
            parent_id = parent_ids.get(act["parent"])
            if parent_id is None:
                fail(3, f"找不到父页「{act['parent']}」的 page id，无法挂载 {act['title']}")
        payload = {
            "type": "page",
            "title": act["title"],
            "space": {"key": space},
            "body": {"storage": {"value": act["body"], "representation": "storage"}},
        }
        if kind == "create":
            payload["ancestors"] = [{"id": parent_id}]
            page = confluence("POST", "/rest/api/content", payload=payload)
            created += 1
        else:
            payload["id"] = act["page_id"]
            payload["version"] = {
                "number": act["version"] + 1,
                "message": "catalog: 挪回正确类别页" if kind == "move" else "catalog: 由仓库同步",
            }
            if kind == "move":
                payload["ancestors"] = [{"id": parent_id}]
            page = confluence("PUT", f"/rest/api/content/{act['page_id']}", payload=payload)
            if kind == "move":
                moved += 1
            else:
                updated += 1
        ensure_label(page["id"])
        record_publish_state(page["id"], act["body"])
        if act["parent"] == "__overview__":
            parent_ids[act["title"]] = page["id"]
    return updated, created, moved, out_of_order, orphaned, skipped


def remote_drift(entries, config):
    """比对 Confluence 页面与仓库，返回 [(状态, 标题, 说明)]。只读。

    状态：OK 与仓库一致 / STALE 页面落后于仓库 / DRIFT 页面被手工编辑过 /
    MISPLACED 父页不对（publish --apply 会挪回）/ MISSING Confluence 上没有。
    """
    space = config["confluence"]["space_key"]
    home_id = space_homepage_id(space)
    home = confluence("GET", f"/rest/api/content/{home_id}", params={"expand": "body.storage"})
    home_children = {
        child["title"]: child for child in list_children(home_id, expand="version,body.storage")
    }

    pages = expected_pages(entries, config)
    cat_titles = {title for _, title, _, parent in pages if parent == "__overview__"}

    # 标题 → [(page, 父页标题；None = 挂在首页下)]；同名页挂错地方也能被看到
    found = {}
    for title, child in home_children.items():
        if title not in cat_titles:
            found.setdefault(title, []).append((child, None))
    for title in (t for _, t, _, parent in pages if parent == "__overview__"):
        cat_page = home_children.get(title)
        if cat_page is None:
            continue
        for child in list_children(cat_page["id"], expand="version,body.storage"):
            found.setdefault(child["title"], []).append((child, title))

    rows = []
    for key, title, body, parent in pages:
        if parent is None:
            current = home
        elif parent == "__overview__":
            current = home_children.get(title)
            if current is None:
                rows.append(("MISSING", title, "Confluence 上没有这一页 —— 跑 publish --apply"))
                continue
        else:
            candidates = found.get(title) or []
            correct = [page for page, pt in candidates if pt == parent]
            if not candidates:
                rows.append(("MISSING", title, "Confluence 上没有这一页 —— 跑 publish --apply"))
                continue
            current = correct[0] if correct else candidates[0][0]
            if not correct:
                rows.append(
                    ("MISPLACED", title, f"父页不对，应挂在 {parent} 下 —— 跑 publish --apply 挪回")
                )
                continue
        state = get_page_property(current["id"])
        if not state:
            rows.append(("DRIFT", title, "页面没有 catalog 记录 —— 不是本脚本发布的"))
            continue
        stored = ((current.get("body") or {}).get("storage") or {}).get("value", "")
        if body_hash(stored) != state.get("body_hash"):
            rows.append(("DRIFT", title, "页面被手工编辑过 —— publish --apply 会覆盖"))
        elif state.get("repo_hash") != body_hash(body):
            rows.append(("STALE", title, "页面落后于仓库 —— 跑 publish --apply"))
        else:
            rows.append(("OK", title, "与仓库一致"))
    return rows


def cmd_publish(args):
    """publish：把仓库内容发布到 Confluence；默认 dry-run，--apply 才写入。"""
    entries = collect_entries()
    errors = validate(entries)
    if errors:
        for err in errors:
            print(f"[ERR]  {err}", file=sys.stderr)
        fail(1, "元数据有错，先跑 check 修好再 publish")

    config = load_config()
    space = config["confluence"]["space_key"]
    if not space or space.startswith("<"):
        fail(2, "scripts/catalog.config.json 里的 confluence.space_key 还没填")

    try:
        home_id, actions = build_publish_plan(entries, config)
    except ConfluenceError as exc:
        fail(3, f"Confluence 调用失败 / request failed: {exc}\n  检查凭据: {CONFLUENCE_CONFIG}")

    print(f"[INFO] 空间 / space: {space}（首页 id {home_id}，总览页复用它）")
    for act in actions:
        print(f"  [{act['kind']:8}] {act['title']}")

    if not args.apply:
        print("\n[INFO] dry-run（未写入 Confluence）。确认无误后加 --apply 实际发布")
        return 0

    try:
        updated, created, moved, out_of_order, orphaned, skipped = apply_publish(config, home_id, actions)
    except ConfluenceError as exc:
        fail(3, f"发布失败 / publish failed: {exc}")
    print(
        f"[SYNC] 更新 {updated} 页、新建 {created} 页、挪回 {moved} 页、"
        f"顺序待手工拖动 {out_of_order} 处、标记 {orphaned} 个孤儿、跳过 {skipped} 页（已是最新）"
    )
    print(f"[SYNC] {confluence_client()['base']}/display/{space}")
    return 0


def cmd_sync(args):
    """sync：build + publish 一次跑完；默认 dry-run，--apply 才落盘并写 Confluence。"""
    status = cmd_build(args)
    if status:
        return status
    print()
    return cmd_publish(args)


def main():
    """解析子命令并分发。"""
    parser = argparse.ArgumentParser(
        prog="catalog.py",
        description="ai-toolbox 条目元数据的校验与目录生成",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    sub = parser.add_subparsers(dest="command")

    check = sub.add_parser("check", help="只校验元数据（只读）")
    check.add_argument("--remote", action="store_true", help="额外比对 Confluence 页面是否漂移（只读）")
    check.set_defaults(func=cmd_check)

    build = sub.add_parser("build", help="生成 README（目录表 + 各条目的维护者行）与 Confluence payload")
    build.add_argument("--apply", action="store_true", help="实际写入（默认 dry-run）")
    build.set_defaults(func=cmd_build)

    publish = sub.add_parser("publish", help="发布到 Confluence")
    publish.add_argument("--apply", action="store_true", help="实际写入 Confluence（默认 dry-run）")
    publish.set_defaults(func=cmd_publish)

    sync = sub.add_parser("sync", help="build + publish 一次跑完")
    sync.add_argument("--apply", action="store_true", help="实际落盘并写入 Confluence（默认 dry-run）")
    sync.set_defaults(func=cmd_sync)

    bump = sub.add_parser("bump", help="给某个条目升一级版本号（默认 patch）")
    bump.add_argument("name", help="条目名（目录名，如 jira）")
    level = bump.add_mutually_exclusive_group()
    level.add_argument("--major", dest="kind", action="store_const", const="major", help="主版本 +1")
    level.add_argument("--minor", dest="kind", action="store_const", const="minor", help="次版本 +1")
    level.add_argument("--patch", dest="kind", action="store_const", const="patch", help="修订号 +1（默认）")
    bump.set_defaults(func=cmd_bump, kind="patch")

    args = parser.parse_args()
    if not getattr(args, "func", None):
        parser.print_help()
        sys.exit(2)
    sys.exit(args.func(args))


if __name__ == "__main__":
    main()
