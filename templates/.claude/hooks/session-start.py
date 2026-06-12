#!/usr/bin/env python3
"""
session-start hook（SessionStart）

会话启动时：
1. 注入当前 Phase 状态、ROADMAP 章节、PLAN
2. 检测 last-session.json，如果存在则调用 Claude API 解析 transcript
   - 非正常结束（有进行中的 layer）→ 输出恢复摘要，等待开发者确认继续
   - 正常结束（无进行中的 layer）→ 提示下一个 Phase，等待开发者确认开启

触发时机：Claude Code 会话启动时（startup、resume、clear、compact）
"""

import json
import sys
import urllib.request
from pathlib import Path
from datetime import datetime, timezone


def find_project_root() -> Path:
    current = Path.cwd()
    for parent in [current] + list(current.parents):
        if (parent / "ROADMAP.md").exists():
            return parent
    return current


def read_file_safe(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except FileNotFoundError:
        return ""


def parse_state(state_content: str) -> dict:
    state = {
        "current_phase": None,
        "current_layer": None,
        "phase_rows": [],
    }
    lines = state_content.splitlines()
    for i, line in enumerate(lines):
        stripped = line.strip()
        if stripped.startswith("## Current Phase"):
            for j in range(i + 1, len(lines)):
                val = lines[j].strip()
                if val:
                    state["current_phase"] = val
                    break
        elif stripped.startswith("## Current Layer"):
            for j in range(i + 1, len(lines)):
                val = lines[j].strip()
                if val:
                    state["current_layer"] = val
                    break
        elif "|" in line and "---" not in line and "Phase" not in line:
            parts = [p.strip() for p in line.split("|") if p.strip()]
            if len(parts) >= 3:
                state["phase_rows"].append({
                    "number": parts[0],
                    "name": parts[1],
                    "status": parts[2],
                })
    return state


def extract_phase_section(roadmap_content: str, phase_number: str) -> str:
    lines = roadmap_content.splitlines()
    in_section = False
    section_lines = []
    for line in lines:
        if line.startswith(f"## Phase {phase_number}"):
            in_section = True
            section_lines.append(line)
        elif in_section:
            if line.startswith("## Phase ") and f"## Phase {phase_number}" not in line:
                break
            section_lines.append(line)
    return "\n".join(section_lines)


def get_next_pending_phase(phase_rows: list) -> dict | None:
    for row in phase_rows:
        if row["status"] == "pending":
            return row
    return None


def read_transcript(transcript_path: str, max_messages: int = 30) -> str:
    """
    读取 transcript .jsonl 文件，提取最后 N 条消息内容。
    只取 assistant 消息，避免注入过多内容。
    """
    try:
        path = Path(transcript_path)
        if not path.exists():
            return ""

        lines = path.read_text(encoding="utf-8").strip().splitlines()
        messages = []

        for line in lines:
            try:
                entry = json.loads(line)
                role = entry.get("role", "")
                if role == "assistant":
                    content = entry.get("content", "")
                    if isinstance(content, list):
                        # content 可能是 block 列表
                        text_parts = [
                            block.get("text", "")
                            for block in content
                            if isinstance(block, dict) and block.get("type") == "text"
                        ]
                        content = "\n".join(text_parts)
                    if content:
                        messages.append(f"[assistant]\n{content}")
            except (json.JSONDecodeError, KeyError):
                continue

        # 只取最后 max_messages 条
        recent = messages[-max_messages:]
        return "\n\n---\n\n".join(recent)

    except Exception as e:
        return f"[transcript 读取失败：{e}]"


def call_claude_api(prompt: str) -> str:
    """调用 Claude API 解析 transcript 内容"""
    try:
        payload = {
            "model": "claude-sonnet-4-20250514",
            "max_tokens": 1000,
            "messages": [
                {"role": "user", "content": prompt}
            ]
        }

        req = urllib.request.Request(
            "https://api.anthropic.com/v1/messages",
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "Content-Type": "application/json",
                "anthropic-version": "2023-06-01",
            },
            method="POST"
        )

        with urllib.request.urlopen(req, timeout=30) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            content = data.get("content", [])
            return "\n".join(
                block.get("text", "")
                for block in content
                if isinstance(block, dict) and block.get("type") == "text"
            )

    except Exception as e:
        return f"[API 调用失败：{e}]"


def analyze_last_session(last_session: dict, project_root: Path) -> str:
    """
    解析上次会话记录，判断正常结束还是非正常结束，返回注入内容。
    """
    transcript_path = last_session.get("transcript_path", "")
    has_active_layer = last_session.get("has_active_layer", False)
    phase = last_session.get("phase", "")
    phase_name = last_session.get("phase_name", "")
    layer = last_session.get("layer", "")
    ended_at = last_session.get("ended_at", "")

    transcript_content = read_transcript(transcript_path)

    if has_active_layer:
        # 非正常结束：有进行中的 layer，需要恢复
        prompt = f"""以下是上次开发会话的助手消息记录（最近30条）：

{transcript_content}

---
上次会话信息：
- Phase {phase}：{phase_name}
- 进行中的技术层：{layer}
- 会话结束时间：{ended_at}

请基于以上记录，简洁总结：
1. 已完成的任务（精确到方法/类级别）
2. 中断时未完成的任务
3. 建议的接续点

输出格式为纯文本，不超过300字。"""

        summary = call_claude_api(prompt)

        return f"""## ⚠️ 检测到上次会话中断（PhaseFlow 自动恢复）

**上次会话**：Phase {phase} {phase_name} — {layer}
**结束时间**：{ended_at}

### 上次执行摘要
{summary}

### 确认后继续
请确认以上摘要无误后，告诉我"继续执行"即可从断点恢复。
如有出入请告知，我会重新理解后再继续。
不要在确认前开始写代码。"""

    else:
        # 正常结束：无进行中的 layer
        state_content = read_file_safe(project_root / "STATE.md")
        state = parse_state(state_content)
        next_phase = get_next_pending_phase(state["phase_rows"])

        if next_phase:
            return f"""## ✅ 上次会话正常结束（PhaseFlow）

**上次会话**：Phase {phase} {phase_name}
**结束时间**：{ended_at}

### 下一步
下一个待执行的 Phase：**Phase {next_phase['number']}：{next_phase['name']}**

准备好后执行 `/phase-plan {next_phase['number']}` 开始。"""

        else:
            return f"""## ✅ 上次会话正常结束（PhaseFlow）

**上次会话**：Phase {phase} {phase_name}
**结束时间**：{ended_at}

所有 Phase 已完成，下一步进入集成验收阶段：
执行 gstack `/review` → `/qa` → `/cso`"""


def build_state_injection(project_root: Path) -> str:
    """构建基础状态注入内容"""
    roadmap_content = read_file_safe(project_root / "ROADMAP.md")
    state_content = read_file_safe(project_root / "STATE.md")

    if not roadmap_content and not state_content:
        return ""

    state = parse_state(state_content)
    current_phase = state["current_phase"]
    current_layer = state["current_layer"]

    parts = [
        "## 当前项目状态（PhaseFlow 自动注入）\n",
    ]

    if state["phase_rows"]:
        parts.append("**Phase 状态总览**")
        for row in state["phase_rows"]:
            icon = {"completed": "✅", "in_progress": "🔄", "pending": "⏳"}.get(row["status"], "❓")
            parts.append(f"  {icon} Phase {row['number']}：{row['name']} ({row['status']})")
        parts.append("")

    parts.append(f"**当前 Phase**：{current_phase or '未开始'}")
    if current_layer and current_layer != "-":
        parts.append(f"**当前技术层**：{current_layer}")
    parts.append("")

    if current_phase and roadmap_content:
        phase_section = extract_phase_section(roadmap_content, current_phase)
        if phase_section:
            parts.append("### 当前 Phase 定义")
            parts.append(phase_section)
            parts.append("")

    plan_content = read_file_safe(project_root / "PLAN.md")
    if plan_content:
        parts.append("### 当前执行计划（PLAN.md）")
        parts.append(plan_content)
        parts.append("")

    parts.append("### 执行规则")
    parts.append("- 接口文档在 docs/api/，实现必须严格遵循，发现问题停下来报告")
    parts.append("- 每层 /review 通过后手动执行 /phase-contract 生成契约文件")
    parts.append("- Phase 所有层完成后执行 /phase-verify，STATE 只由 verify 更新")

    return "\n".join(parts)


def main():
    try:
        hook_input = json.loads(sys.stdin.read())
    except (json.JSONDecodeError, ValueError):
        hook_input = {}

    try:
        project_root = find_project_root()

        if not (project_root / "ROADMAP.md").exists():
            sys.exit(0)

        parts = []

        # 1. 检测 last-session.json
        last_session_path = project_root / "docs" / "handoffs" / "last-session.json"
        if last_session_path.exists():
            try:
                last_session = json.loads(last_session_path.read_text(encoding="utf-8"))
                session_analysis = analyze_last_session(last_session, project_root)
                if session_analysis:
                    parts.append(session_analysis)
                    parts.append("")
            except Exception as e:
                parts.append(f"[PhaseFlow] last-session.json 解析失败：{e}")
                parts.append("")

        # 2. 基础状态注入
        state_injection = build_state_injection(project_root)
        if state_injection:
            parts.append(state_injection)

        if parts:
            result = {
                "additionalContext": "\n".join(parts)
            }
            print(json.dumps(result, ensure_ascii=False))

    except Exception as e:
        print(f"[session-start hook error] {e}", file=sys.stderr)

    sys.exit(0)


if __name__ == "__main__":
    main()
