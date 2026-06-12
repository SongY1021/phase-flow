#!/usr/bin/env python3
"""
brainstorming-pre hook（PreToolUse）

在 Superpowers /brainstorming 触发前，自动注入完整的架构约束上下文：
- docs/arch-review.md（全局数据模型和架构决策）
- docs/api/[当前模块].md（接口契约）
- docs/security-review.md（横切安全约束）
- docs/contracts/[当前模块]-[前置层].md（模块内层间契约，完整内容）
- docs/contracts/[依赖模块]-service.md 的"对外接口"章节（跨模块依赖）

触发时机：检测到 /brainstorming 命令或 Superpowers brainstorming skill 激活时
"""

import json
import re
import sys
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


def get_current_state(project_root: Path) -> dict:
    """从 STATE.md 提取当前 Phase 和技术层"""
    state_content = read_file_safe(project_root / "STATE.md")
    state = {"current_phase": None, "current_layer": None}

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

    return state


def get_module_name_from_plan(project_root: Path) -> str:
    """从 PLAN.md 标题提取模块名，格式：# PLAN - Phase N：模块名"""
    plan_content = read_file_safe(project_root / "PLAN.md")
    for line in plan_content.splitlines():
        if line.startswith("# PLAN"):
            parts = line.split("：", 1)
            if len(parts) > 1:
                return parts[1].strip()
    return ""


def module_name_to_key(name: str) -> str:
    """将中文模块名转换为文件名 key，与 /phase-contract 生成规则保持一致"""
    return name.lower().replace(" ", "-").replace("_", "-")


def get_api_doc(project_root: Path, module_name: str) -> str:
    """查找当前模块的 API 文档"""
    api_dir = project_root / "docs" / "api"
    if not api_dir.exists():
        return ""

    key = module_name_to_key(module_name)
    candidates = [f"{key}.md", f"{key.replace('-', '_')}.md"]

    for candidate in candidates:
        path = api_dir / candidate
        if path.exists():
            return path.read_text(encoding="utf-8")

    available = [f.name for f in api_dir.glob("*.md")]
    return f"[未找到 {module_name} 的 API 文档，可用文件：{available}，请检查命名]"


def get_intra_module_contracts(
    project_root: Path, module_name: str, current_layer: str
) -> str:
    """
    模块内层间契约注入（完整内容）：
    - 服务层 brainstorming → 注入 {模块}-data.md
    - API 层 brainstorming  → 注入 {模块}-data.md + {模块}-service.md
    """
    contracts_dir = project_root / "docs" / "contracts"
    if not contracts_dir.exists():
        return ""

    layer_map = {
        "数据层": [],
        "服务层": ["data"],
        "API 层": ["data", "service"],
        "Layer 1": [],
        "Layer 2": ["data"],
        "Layer 3": ["data", "service"],
    }

    required_layers = []
    for key, layers in layer_map.items():
        if key in current_layer:
            required_layers = layers
            break

    if not required_layers:
        return ""

    module_key = module_name_to_key(module_name)
    parts = []

    for layer in required_layers:
        contract_path = contracts_dir / f"{module_key}-{layer}.md"
        if contract_path.exists():
            content = contract_path.read_text(encoding="utf-8")
            parts.append(f"### 模块内前置契约：{module_key}-{layer}\n{content}")
        else:
            parts.append(
                f"### ⚠️ 前置契约缺失：{module_key}-{layer}.md\n"
                f"请确认上一技术层已完成，Stop hook 已自动触发生成 contract。"
            )

    return "\n\n".join(parts)


def extract_public_interface_section(contract_content: str) -> str:
    """
    从 -service.md contract 中提取"对外接口"章节。
    跨模块注入时只暴露对外接口，不暴露内部实现约定。
    """
    lines = contract_content.splitlines()
    in_section = False
    result_lines = []

    for line in lines:
        if re.match(r"^##\s*对外接口", line):
            in_section = True
            result_lines.append(line)
            continue
        if in_section:
            # 遇到下一个同级章节时停止
            if re.match(r"^##\s", line) and not re.match(r"^##\s*对外接口", line):
                break
            result_lines.append(line)

    if not result_lines:
        # 如果没有分区，说明 contract 格式不符合规范，返回提示
        return "[⚠️ 该 contract 未包含"对外接口"章节，请检查 /phase-contract 是否按规范生成]"

    return "\n".join(result_lines)


def get_cross_module_contracts(
    project_root: Path, current_phase: str, current_layer: str
) -> str:
    """
    跨模块依赖契约注入：
    - 从 ROADMAP.md 读取当前 Phase 的依赖声明
    - 找到每个依赖模块的 -service.md contract
    - 只注入"对外接口"章节（SpringBean 调用只需方法签名 + 业务语义）
    - 仅在服务层 brainstorming 时注入（数据层和 API 层不存在跨模块 service 依赖）
    """
    # 跨模块 service 依赖只在服务层 brainstorming 时注入
    is_service_layer = "服务层" in current_layer or "Layer 2" in current_layer
    if not is_service_layer:
        return ""

    roadmap_content = read_file_safe(project_root / "ROADMAP.md")
    if not roadmap_content:
        return ""

    contracts_dir = project_root / "docs" / "contracts"
    if not contracts_dir.exists():
        return ""

    # 定位当前 Phase 章节，提取依赖声明
    lines = roadmap_content.splitlines()
    in_phase = False
    dependent_phase_numbers = []

    for line in lines:
        if re.match(rf"^##\s*Phase\s*{current_phase}[：:]", line):
            in_phase = True
            continue
        if in_phase:
            if line.startswith("## Phase ") and f"Phase {current_phase}" not in line:
                break
            # 匹配"依赖：Phase 1, Phase 2"或"依赖：Phase 1"格式
            dep_match = re.search(r"依赖[：:]\s*(.+)", line)
            if dep_match:
                dep_str = dep_match.group(1)
                # 提取所有 Phase 编号
                numbers = re.findall(r"Phase\s*(\d+)", dep_str)
                dependent_phase_numbers.extend(numbers)

    if not dependent_phase_numbers:
        return ""

    # 根据依赖的 Phase 编号找到对应模块名，读取其 -service.md 对外接口
    parts = []

    for dep_num in dependent_phase_numbers:
        # 从 ROADMAP 中找到依赖 Phase 的模块名
        dep_module_name = ""
        in_dep_phase = False
        for line in lines:
            if re.match(rf"^##\s*Phase\s*{dep_num}[：:]", line):
                in_dep_phase = True
                name_parts = line.split("：", 1)
                if len(name_parts) > 1:
                    dep_module_name = name_parts[1].strip()
                break

        if not dep_module_name:
            continue

        dep_module_key = module_name_to_key(dep_module_name)
        service_contract_path = contracts_dir / f"{dep_module_key}-service.md"

        if service_contract_path.exists():
            content = service_contract_path.read_text(encoding="utf-8")
            public_section = extract_public_interface_section(content)
            parts.append(
                f"### 跨模块依赖契约：Phase {dep_num} {dep_module_name}（对外接口）\n"
                f"{public_section}"
            )
        else:
            parts.append(
                f"### ⚠️ 跨模块依赖契约缺失：Phase {dep_num} {dep_module_name}\n"
                f"期望文件：{dep_module_key}-service.md\n"
                f"请确认依赖 Phase 已完成并生成 contract。"
            )

    return "\n\n".join(parts)


def extract_arch_review_preview(content: str, max_h2_sections: int = 3) -> str:
    """提取 arch-review 的核心部分，避免注入过多内容"""
    lines = content.splitlines()
    preview_lines = []
    h2_count = 0

    for line in lines:
        preview_lines.append(line)
        if line.startswith("## "):
            h2_count += 1
            if h2_count > max_h2_sections:
                preview_lines.append("...（完整内容见 docs/arch-review.md）")
                break

    return "\n".join(preview_lines)


def build_brainstorming_context(project_root: Path) -> str:
    """构建注入到 brainstorming 前的完整架构上下文"""

    state = get_current_state(project_root)
    module_name = get_module_name_from_plan(project_root)
    current_layer = state.get("current_layer", "")
    current_phase = state.get("current_phase", "")

    parts = [
        "## ⚡ Brainstorming 架构约束上下文（自动注入）",
        "",
        f"**当前任务**：Phase {current_phase} {module_name} — {current_layer}",
        "",
        "**重要**：以下内容是已确认的架构决策，brainstorming 只做实现设计，不重新推导架构。",
        "",
    ]

    # 1. arch-review.md
    arch_review = read_file_safe(project_root / "docs" / "arch-review.md")
    if arch_review:
        parts.append("### 架构决策（arch-review.md 摘要）")
        parts.append(extract_arch_review_preview(arch_review))
        parts.append("")

    # 2. 当前模块 API 文档
    if module_name:
        api_doc = get_api_doc(project_root, module_name)
        if api_doc:
            parts.append(f"### 接口契约（docs/api/{module_name_to_key(module_name)}.md）")
            parts.append(api_doc)
            parts.append("")

    # 3. security-review.md
    security_review = read_file_safe(project_root / "docs" / "security-review.md")
    if security_review:
        sec_lines = security_review.splitlines()
        preview = "\n".join(sec_lines[:60])
        if len(sec_lines) > 60:
            preview += "\n...（完整内容见 docs/security-review.md）"
        parts.append("### 安全约束（security-review.md 摘要）")
        parts.append(preview)
        parts.append("")

    # 4. 模块内层间契约（完整内容）
    if module_name and current_layer:
        intra_contracts = get_intra_module_contracts(project_root, module_name, current_layer)
        if intra_contracts:
            parts.append("### 模块内前置层契约")
            parts.append(intra_contracts)
            parts.append("")

    # 5. 跨模块依赖契约（仅服务层，只注入对外接口章节）
    if current_phase and current_layer:
        cross_contracts = get_cross_module_contracts(
            project_root, current_phase, current_layer
        )
        if cross_contracts:
            parts.append("### 跨模块依赖契约（SpringBean 调用接口）")
            parts.append(cross_contracts)
            parts.append("")

    # 6. 当前层执行范围（来自 PLAN.md）
    plan_content = read_file_safe(project_root / "PLAN.md")
    if plan_content and current_layer:
        plan_lines = plan_content.splitlines()
        in_layer = False
        layer_lines = []
        for line in plan_lines:
            if (current_layer in line or current_layer.replace("：", ":") in line) and (
                line.startswith("## Layer") or line.startswith("## 层")
            ):
                in_layer = True
                layer_lines.append(line)
                continue
            if in_layer:
                if (line.startswith("## Layer") or line.startswith("---")) and layer_lines:
                    break
                layer_lines.append(line)

        if layer_lines:
            parts.append("### 本层执行范围（来自 PLAN.md）")
            parts.append("\n".join(layer_lines))
            parts.append("")

    # 7. 执行边界提示
    parts.append("### Brainstorming 执行边界")
    parts.append("- 范围：仅限 PLAN.md 中本层列出的文件，不得跨层修改")
    parts.append("- 架构决策已定，不重新讨论数据模型或模块划分")
    parts.append("- 发现 API 文档与需求不符时，停下来报告，不自行修改")
    parts.append("- 跨模块调用只使用上方"对外接口"中列出的方法，不直接依赖对方数据层")

    return "\n".join(parts)


def main():
    try:
        hook_input = {}
        if not sys.stdin.isatty():
            try:
                hook_input = json.loads(sys.stdin.read())
            except (json.JSONDecodeError, ValueError):
                pass

        tool_name = hook_input.get("tool_name", "")
        command = hook_input.get("command", "")

        is_brainstorming = (
            "brainstorming" in tool_name.lower()
            or "brainstorming" in command.lower()
        )

        if not is_brainstorming:
            print(json.dumps({"type": "no_op"}))
            return

        project_root = find_project_root()

        if not (project_root / "ROADMAP.md").exists():
            print(json.dumps({"type": "no_op"}))
            return

        context = build_brainstorming_context(project_root)

        result = {
            "type": "context_injection",
            "content": context,
            "inject_position": "before_tool",
        }
        print(json.dumps(result, ensure_ascii=False))

    except Exception as e:
        print(f"[brainstorming-pre hook error] {e}", file=sys.stderr)
        print(json.dumps({"type": "no_op"}))


if __name__ == "__main__":
    main()
