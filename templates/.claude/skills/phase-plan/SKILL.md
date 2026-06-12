---
name: phase-plan
description: 【PhaseFlow】将 ROADMAP 中的当前 Phase（功能模块）拆分为有序的技术层执行计划，产出 PLAN.md，作为 Superpowers brainstorming 的输入边界。在每个 Phase 开始执行前触发。用户说"开始执行 Phase N"、"规划 Phase N"、"生成执行计划"时使用此工具。
---

# PhaseFlow — phase-plan

将 ROADMAP 中的功能模块拆分为有序的技术层执行序列，为 Superpowers 提供明确的执行边界。

## 核心职责

ROADMAP 定义"做什么"，PLAN 定义"分几层做、每层范围是什么"。
Superpowers brainstorming 的粒度是单个技术层，PLAN 的作用是给每次 brainstorming 提供明确的输入边界，防止范围蔓延。

## 前置条件

- `ROADMAP.md` 存在
- `STATE.md` 存在，且目标 Phase 状态为 `in_progress`
- `docs/arch-review.md` 存在
- `docs/api/[对应模块].md` 存在

## 执行步骤

### Step 1：读取上下文

1. 读取 `ROADMAP.md`，定位目标 Phase，提取：目标、文件范围、验收标准
2. 读取 `STATE.md`，确认当前 Phase 编号
3. 读取 `docs/arch-review.md`，提取目标模块的数据模型和依赖关系
4. 读取 `docs/api/[模块名].md`，提取接口契约约束
5. 读取 `docs/security-review.md`，提取与本模块相关的安全约束
6. 检查 `docs/contracts/` 目录，读取本 Phase 依赖的前置 contract 文件

### Step 2：拆分技术层

标准三层结构（如无特殊情况不得调整顺序）：

```
数据层 → 服务层 → API 层
```

每层的拆分要点：

**数据层**
- 实体类、数据库 Schema、Migration
- Repository 接口定义
- 不包含任何业务逻辑

**服务层**
- 业务逻辑实现
- 与外部系统（如堡垒机）的交互
- 事务管理、异常处理
- 依赖数据层接口，不依赖 HTTP 层

**API 层**
- Controller、DTO、路由
- 鉴权中间件集成
- 严格遵循 `docs/api/[模块名].md`，不允许自行修改接口定义

### Step 3：生成 PLAN.md

输出路径：项目根目录 `PLAN.md`（每次执行新 Phase 时覆盖）

```markdown
# PLAN - Phase {N}：{模块名}

> 生成时间：{date}
> Phase 目标：{来自 ROADMAP 的目标}

## 架构约束（所有层共同遵守）
- {来自 arch-review.md 的关键约束，如 tenant_id 隔离}
- {来自 security-review.md 的安全约束}
- {前置 contract 中的接口契约约束}

## Layer 1：数据层

**任务范围**
- {具体文件列表，精确到类名}

**接口约束**
- {服务层将通过哪些方法访问数据层，需要在此层定义}

**注意事项**
- {特殊字段处理、索引要求等}

**完成后**：执行 Superpowers /review，/review 通过后手动执行 `/phase-contract {N} data`

---

## Layer 2：服务层

**前置依赖**：Layer 1 完成，`docs/contracts/{模块}-data.md` 已生成

**任务范围**
- {具体文件列表}

**接口约束**
- {API 层将通过哪些方法调用服务层}
- {外部系统调用约束（如堡垒机接口）}

**注意事项**
- {双写逻辑、事务边界等}

**完成后**：执行 Superpowers /review，/review 通过后手动执行 `/phase-contract {N} service`

---

## Layer 3：API 层

**前置依赖**：Layer 2 完成，`docs/contracts/{模块}-service.md` 已生成

**任务范围**
- {具体文件列表}

**强制约束**：严格遵循 `docs/api/{模块名}.md`，发现文档问题停下来报告，不允许自行修改接口后继续。

**完成后**：执行 Superpowers /review，/review 通过后手动执行 `/phase-contract {N} api`

---

## 验收标准
{直接复制自 ROADMAP.md 对应 Phase 的验收标准}
```

### Step 4：更新 STATE.md

在 `STATE.md` 的 `Current Layer` 字段填入 `Layer 1：数据层`。

### Step 5：提示执行入口

```
PLAN.md 已生成。

执行顺序：
  Layer 1（数据层）→ Superpowers TDD → /review → /phase-contract {N} data
  Layer 2（服务层）→ Superpowers TDD → /review → /phase-contract {N} service
  Layer 3（API 层）→ Superpowers TDD → /review → /phase-contract {N} api
  → /phase-verify {N}

现在可以开始 Layer 1，请执行 Superpowers /brainstorming。
注意：brainstorming 的范围限定为 PLAN.md Layer 1 中列出的文件。
```
