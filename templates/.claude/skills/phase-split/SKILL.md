---
name: phase-split
description: 【PhaseFlow】基于 arch-review.md 和 security-review.md 生成标准化的 ROADMAP.md 与初始 STATE.md。在决策阶段完成后（arch-review + security-review + API 文档均已就绪）触发。用户说"开始拆分 Phase"、"生成 ROADMAP"、"进入执行阶段"时使用此工具。
---

# PhaseFlow — phase-split

将决策阶段产出物转化为可执行的 Phase 路线图，并初始化状态追踪文件。

## 前置条件

执行前确认以下文件存在：
- `docs/arch-review.md`
- `docs/security-review.md`
- `docs/api/*.md`（至少存在公共定义文件）

如有缺失，停止并告知用户补全后再执行。

## 执行步骤

### Step 1：读取决策文档

依次读取：
1. `docs/arch-review.md` — 提取：模块列表、数据模型、模块间依赖关系
2. `docs/security-review.md` — 提取：横切安全约束（租户隔离、凭据存储等）

### Step 2：拆分原则

**模块间依赖顺序**（决定 Phase 顺序）：
- 被其他模块依赖的先做
- 互相独立的模块可标记为可并行
- 横切基础设施（多租户、同步队列等）必须最先完成

**Phase 粒度**：功能模块级（一个完整业务模块 = 一个 Phase）。
技术层内的拆分（数据层/服务层/API 层）不在 ROADMAP 中展开，由 `/phase-plan` 在执行前细化。

**每个 Phase 必须包含**：
- 目标（一句话）
- 依赖（前置 Phase 编号，无则填"无"）
- 可否与其他 Phase 并行
- 文件范围（涉及的主要文件或目录）
- 验收标准（可测试的具体条件，不少于 2 条）

### Step 3：生成 ROADMAP.md

输出路径：项目根目录 `ROADMAP.md`

```markdown
# ROADMAP

> 生成时间：{date}
> 基于：docs/arch-review.md + docs/security-review.md

## Phase 1：{模块名}
- **目标**：{一句话描述}
- **依赖**：无
- **并行**：不可并行（第一个 Phase）
- **文件范围**：{主要文件列表}
- **验收标准**：
  - {可测试条件 1}
  - {可测试条件 2}

## Phase 2：{模块名}
- **目标**：{一句话描述}
- **依赖**：Phase 1
- **并行**：可与 Phase 3 并行
- **文件范围**：{主要文件列表}
- **验收标准**：
  - {可测试条件 1}
  - {可测试条件 2}

（以此类推）
```

### Step 4：生成 STATE.md

输出路径：项目根目录 `STATE.md`

```markdown
# PROJECT STATE

## Current Phase
1

## Current Layer
-

## Phase Status
| Phase | Name | Status |
|-------|------|--------|
| 1 | {模块名} | in_progress |
| 2 | {模块名} | pending |
| 3 | {模块名} | pending |
| ... | ... | pending |

## Last Updated
{ISO 8601 timestamp}
```

Status 只有三个值：`pending` / `in_progress` / `completed`

初始状态：Phase 1 为 `in_progress`，其余全部 `pending`。
`Current Layer` 初始为空，由 `/phase-plan` 执行后填入。

### Step 5：确认输出

生成完成后，向用户展示：
1. Phase 总数和各 Phase 名称列表
2. 关键依赖链（哪些 Phase 必须串行）
3. 可并行的 Phase 组合

提示下一步：执行 `/phase-plan 1` 开始第一个 Phase。
