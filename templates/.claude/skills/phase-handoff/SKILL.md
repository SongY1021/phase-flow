---
name: phase-handoff
description: 【PhaseFlow】在会话中断前，手动补充自动记录无法捕获的执行上下文（已知问题、特殊决策、注意事项等），写入 last-session.json 的 notes 字段，供新会话恢复时参考。SessionEnd hook 已自动记录 transcript 和状态信息，此工具仅用于补充人工备注。用户说"补充中断备注"、"记录注意事项"时触发。
---

# PhaseFlow — phase-handoff

在会话中断前，补充自动记录无法捕获的人工备注，增强新会话的恢复质量。

## 核心定位

SessionEnd hook 已自动处理：
- transcript_path 记录
- session_id 和时间戳
- 当前 Phase 和 layer 状态
- 新会话的 transcript 解析和恢复判断

此工具只负责补充**人工判断的上下文**，比如：
- 当前遇到的技术难题和已尝试的方案
- 偏离 arch-review 的设计决策及原因
- 需要下一个会话特别注意的事项
- 发现但未处理的潜在 bug

## 使用时机

在准备关闭会话前，如果有以上信息需要传递给下一个会话时触发。
如果没有特别需要补充的信息，不需要执行此工具，SessionEnd hook 会自动处理。

## 执行步骤

### Step 1：询问补充内容

向用户询问：

```
需要补充哪些自动记录无法捕获的信息？

可以包括：
- 当前遇到的技术难题和已尝试的方案
- 偏离架构设计的决策及原因
- 下一个会话需要特别注意的事项
- 发现但未处理的潜在问题
```

### Step 2：写入 last-session.json

读取 `docs/handoffs/last-session.json`（如果已存在），在其中添加 `notes` 字段：

```json
{
  "session_id": "...",
  "transcript_path": "...",
  "ended_at": "...",
  "phase": "...",
  "layer": "...",
  "has_active_layer": true,
  "notes": {
    "recorded_at": "{当前时间}",
    "content": "{用户提供的备注内容}"
  }
}
```

如果 `last-session.json` 不存在（会话尚未结束），先创建基础结构再写入 notes。

### Step 3：确认

```
备注已记录，新会话恢复时将自动读取。
现在可以关闭当前会话。
```
