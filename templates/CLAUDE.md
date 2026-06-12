# CLAUDE.md

## 框架分工

| 框架 | 层次 | 职责 |
|------|------|------|
| gstack | 决策层 | 需求决策、架构评审、安全评审 |
| phase-flow | 流程层 | Phase 管理、状态追踪、契约传递 |
| Superpowers | 执行层 | 单技术层的 TDD 实现 |

---

## 决策阶段（Phase 1-5，gstack 驱动）

```
Phase 1：项目背景输入（Plan Mode）          → 系统理解确认
Phase 2：需求决策澄清（/office-hours）       → docs/office-hours.md
Phase 3：架构评审（/plan-eng-review）        → docs/arch-review.md
Phase 4：接口文档设计                        → docs/api/*.md
Phase 5：安全评审（/cso）                   → docs/security-review.md
```

---

## 执行阶段（Phase 6+，自定义 Skills 驱动）

### Phase 6：拆分

```
/phase-split
→ ROADMAP.md（功能模块级路线图 + 验收标准）
→ STATE.md（初始状态）
```

### Phase N（每个功能模块的标准循环）

```
/phase-plan N
→ PLAN.md（技术层执行序列）

↓ 每个技术层重复以下循环

[技术层执行]
Superpowers /brainstorming    ← brainstorming-pre hook 自动注入架构约束 + 契约上下文
Superpowers /writing-plans
Superpowers TDD + subagent
Superpowers /review
    ↓ Stop hook 自动触发
    → docs/contracts/{模块}-{data|service|api}.md 自动生成

[异常：上下文超过 40% 时]
/phase-handoff N {layer}
→ docs/handoffs/handoff-{模块}-{layer}-partial.md
→ 关闭会话，用恢复模板开启新会话继续

↓ 三层全部完成后

/phase-verify N
→ 验收报告 + STATE.md 更新（唯一写入入口）
→ 进入 Phase N+1
```

### 最终：集成验收（gstack 驱动）

```
读取所有 docs/contracts/ 文件
/review   → 全量代码审查
/qa       → 端到端测试
/cso      → 安全验收
/retro    → 趋势报告
```

---

## 文件职责

| 文件 | 职责 | 写入者 |
|------|------|--------|
| `ROADMAP.md` | Phase 定义 + 验收标准（静态） | /phase-split |
| `STATE.md` | 执行状态（动态） | /phase-verify（唯一写入入口） |
| `PLAN.md` | 当前 Phase 技术层序列 | /phase-plan（每 Phase 覆盖） |
| `docs/contracts/{模块}-data.md` | 数据层接口契约 | Stop hook（/review 后自动） |
| `docs/contracts/{模块}-service.md` | 服务层接口契约（含对外接口/内部约定分区） | Stop hook（/review 后自动） |
| `docs/contracts/{模块}-api.md` | API 层接口契约 | Stop hook（/review 后自动） |
| `docs/handoffs/handoff-{模块}-{layer}-partial.md` | 中断恢复状态 | /phase-handoff（手动，异常路径） |

---

## Contract 分区规范（服务层强制要求）

`-service.md` 必须包含两个明确章节，供 hook 按场景选择性注入：

```markdown
## 对外接口（跨模块可见）
方法签名 + 业务语义 + 约束来源

## 内部实现约定（仅本模块内部参考）
事务边界、外部系统调用约定等
```

跨模块 brainstorming 时只注入"对外接口"章节，模块内层间注入完整 contract。

---

## Hooks 配置

```json
{
  "hooks": [
    {
      "name": "session-start",
      "type": "UserPromptInjection",
      "script": ".claude/hooks/session-start.py",
      "description": "会话启动时注入当前 Phase 状态、ROADMAP 章节、PLAN，检测中断恢复文件"
    },
    {
      "name": "brainstorming-pre",
      "type": "PreToolUse",
      "match": "brainstorming",
      "script": ".claude/hooks/brainstorming-pre.py",
      "description": "brainstorming 前注入 arch-review + API 文档 + security-review + 层间/跨模块 contract"
    },
    {
      "name": "contract-gen",
      "type": "StopHook",
      "match": "review",
      "script": ".claude/hooks/contract-gen.py",
      "description": "Superpowers /review 通过后自动触发 /phase-contract 生成契约文件"
    }
  ]
}
```

---

## 接口文档规则

- 接口文档在 `docs/api/`，**编码前完成，评审通过才能进入实现**
- API 层实现必须严格遵循对应文档
- 发现文档问题：**停下来报告，不允许自行修改接口后继续**

---

## 关键约束

- **STATE.md 只由 /phase-verify 写入**，contract 和 hook 均不修改
- **Contract 由 Stop hook 自动生成**，不需要手动执行
- **上下文超过 40% 主动中断**，执行 /phase-handoff
- **跨模块调用只使用对方的"对外接口"**，不直接依赖对方数据层
- **API 层发现接口文档问题停下来报告**，不自行修改
