# PhaseFlow

> Claude Code 流程驱动开发的 Skills & Hooks 工具集

PhaseFlow 是一套为 **Claude Code + Superpowers** 工作流设计的 Skills 和 Hooks，解决流程驱动模式的两个核心问题：

- **Phase 衔接**：Phase 拆分标准化 + 技术层执行序列 + 状态持久化追踪
- **上下文管理**：契约精准传递 + 中断精确恢复

---

## 设计背景

在 Claude Code 流程驱动开发中，gstack 负责决策层，Superpowers 负责执行层，但两者之间缺少一个流程层来解决：

1. 功能模块如何标准化拆分为有序的技术层执行计划
2. 技术层间、模块间的接口契约如何自动传递给下一次 brainstorming
3. 会话中断后如何精确恢复，而不是从头重来

PhaseFlow 就是这个流程层。

---

## 工具列表

### Skills

| 命令 | 触发时机 | 职责 |
|------|----------|------|
| `/phase-split` | 决策阶段完成后 | 生成 ROADMAP.md + STATE.md |
| `/phase-plan N` | 每个 Phase 开始前 | 生成技术层执行计划 PLAN.md |
| `/phase-contract N {layer}` | 每层 /review 通过后（手动） | 生成层级接口契约 |
| `/phase-handoff N {layer}` | 上下文超 40% 或主动中断时 | 生成中断恢复文件 |
| `/phase-verify N` | Phase 所有层完成后 | 需求完整性验收 + STATE 更新 |

### Hooks

| Hook | 触发时机 | 职责 |
|------|----------|------|
| `session-start` | 每次新会话启动 | 注入当前 Phase 状态 + PLAN，解析上次会话记录 |
| `session-end` | 每次会话结束 | 自动记录 transcript_path 和当前执行状态 |
| `brainstorming-pre` | Superpowers /brainstorming 前 | 注入架构约束 + 层间/跨模块 contract |

---

## 安装

将 `.claude/` 目录和 `CLAUDE.md` 复制到你的项目根目录：

```bash
cp -r .claude/ /your-project/.claude/
cp CLAUDE.md /your-project/CLAUDE.md
```

---

## 完整执行流程

```
决策阶段（gstack Phase 1-5）
→ docs/arch-review.md + docs/security-review.md + docs/api/*.md

/phase-split
→ ROADMAP.md + STATE.md

每个功能模块：

  /phase-plan N
  → PLAN.md

  [数据层]
  Superpowers /brainstorming   ← hook 自动注入架构约束
  Superpowers TDD → /review
  /phase-contract N data       ← 手动触发
  → docs/contracts/{模块}-data.md

  [服务层]
  Superpowers /brainstorming   ← hook 注入 arch + data contract + 跨模块依赖对外接口
  Superpowers TDD → /review
  /phase-contract N service    ← 手动触发
  → docs/contracts/{模块}-service.md

  [API 层]
  Superpowers /brainstorming   ← hook 注入 arch + data + service contract
  Superpowers TDD → /review
  /phase-contract N api        ← 手动触发
  → docs/contracts/{模块}-api.md

  /phase-verify N
  → 验收报告 + STATE.md 更新

集成验收（gstack /review + /qa + /cso）
```

---

## 文件结构

```
.claude/
├── settings.json                       # hooks 配置
├── hooks/
│   ├── session-start.py               # 会话启动恢复 hook
│   ├── session-end.py                 # 会话结束自动记录 hook
│   └── brainstorming-pre.py           # brainstorming 前置注入 hook
└── skills/
    ├── phase-split/SKILL.md
    ├── phase-plan/SKILL.md
    ├── phase-contract/SKILL.md
    ├── phase-handoff/SKILL.md
    └── phase-verify/SKILL.md

CLAUDE.md                               # 框架分工 + 执行规则
```

运行时生成（不纳入版本控制）：

```
ROADMAP.md                              # Phase 定义 + 验收标准
STATE.md                                # 执行状态（唯一写入入口：/phase-verify）
PLAN.md                                 # 当前 Phase 技术层执行序列
docs/contracts/{模块}-{layer}.md        # 层级接口契约
docs/handoffs/handoff-*-partial.md      # 中断恢复文件
```

---

## Contract 分区规范

服务层 contract（`-service.md`）必须包含两个明确章节：

```markdown
## 对外接口（跨模块可见）
方法签名 + 业务语义 + 约束来源

## 内部实现约定（仅本模块内部参考）
事务边界、外部系统调用约定等
```

跨模块 brainstorming 时 hook 只注入"对外接口"章节，避免暴露内部实现细节。

---

## 与 GSD v1 对比

| 维度 | GSD v1 | PhaseFlow |
|------|--------|-----------|
| Phase 拆分 | /gsd-new-project | /phase-split |
| 技术层规划 | /gsd-plan-phase | /phase-plan |
| 状态追踪 | 内置状态机 | STATE.md，/phase-verify 唯一写入 |
| 契约/摘要 | SUMMARY（依赖 execute，与 Superpowers 冲突） | contract（独立于执行层，手动触发） |
| 中断恢复 | /gsd-pause-work | /phase-handoff |
| Phase 验收 | /gsd-verify-work（依赖 SUMMARY） | /phase-verify（依赖 contracts） |
| Superpowers 兼容 | ❌ 执行层强耦合 | ✅ 执行层完全交给 Superpowers |
| 跨模块依赖 | 无明确机制 | service contract 对外接口分区 + hook 选择性注入 |
