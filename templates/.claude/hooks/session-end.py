#!/usr/bin/env python3
"""
session-end hook（SessionEnd）

每次会话结束时自动记录会话信息到 docs/handoffs/last-session.json。
无论正常结束还是中断，都进行记录。
由新会话的 session-start hook 读取并解析判断后续行为。

触发时机：Claude Code 会话结束时（exit、sigint、clear 等）
"""

import json
import sys
from datetime import datetime, timezone
from pathlib import Path


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
        "phase_name": None,
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

    # 从状态表格里找当前 phase 的名称
    for line in lines:
        if state["current_phase"] and f"| {state['current_phase']} |" in line and "in_progress" in line:
            parts = [p.strip() for p in line.split("|") if p.strip()]
            if len(parts) >= 2:
                state["phase_name"] = parts[1]
            break

    return state


def main():
    try:
        hook_input = json.loads(sys.stdin.read())
    except (json.JSONDecodeError, ValueError):
        hook_input = {}

    try:
        project_root = find_project_root()

        # 没有 ROADMAP.md，不是 PhaseFlow 项目，跳过
        if not (project_root / "ROADMAP.md").exists():
            sys.exit(0)

        state_content = read_file_safe(project_root / "STATE.md")
        state = parse_state(state_content)

        # 构建 last-session 记录
        record = {
            "session_id": hook_input.get("session_id", ""),
            "transcript_path": hook_input.get("transcript_path", ""),
            "ended_at": datetime.now(timezone.utc).isoformat(),
            "end_reason": hook_input.get("reason", "unknown"),
            "phase": state["current_phase"],
            "phase_name": state["phase_name"],
            "layer": state["current_layer"],
            # layer 有值说明有进行中的技术层，可能是非正常结束
            # 最终判断由新会话的 session-start hook 通过解析 transcript 来决定
            "has_active_layer": bool(state["current_layer"] and state["current_layer"].strip() and state["current_layer"] != "-"),
        }

        # 确保目录存在
        handoffs_dir = project_root / "docs" / "handoffs"
        handoffs_dir.mkdir(parents=True, exist_ok=True)

        output_path = handoffs_dir / "last-session.json"
        output_path.write_text(
            json.dumps(record, ensure_ascii=False, indent=2),
            encoding="utf-8"
        )

    except Exception as e:
        print(f"[session-end hook error] {e}", file=sys.stderr)

    sys.exit(0)


if __name__ == "__main__":
    main()
