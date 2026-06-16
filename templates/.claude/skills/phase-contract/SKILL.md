---
name: phase-contract
description: 【PhaseFlow】每个技术层（数据层/服务层/API层）的 Superpowers /review 通过后，手动执行生成该层的接口契约文件（contract），供下一层 brainstorming 注入使用。contract 包含接口签名、业务语义和约束来源，是层间与模块间上下文传递的核心载体。
---

# PhaseFlow — phase-contract

记录当前技术层实现后对外暴露的真实接口契约，作为下一层及跨模块 brainstorming 的输入上下文。

## 核心定位

contract 记录的是**已实现并验证的事实 + 设计意图**，不只是代码签名的机械提取。

三个使用场景：
- **模块内层间**：数据层 contract → 服务层 brainstorming；服务层 contract → API 层 brainstorming
- **跨模块**：依赖模块的服务层 contract（对外接口章节）→ 当前模块服务层 brainstorming
- **Phase 验收**：/phase-verify 读取全部 contracts 对照验收标准

与 `arch-review.md` 的区别：arch-review 是规划期的设计意图，contract 是实现后的真实状态，两者都在 brainstorming 时注入，但职责不同。

## 触发方式

每个技术层 Superpowers `/review` 通过后，**手动执行**：

```
/phase-contract {N} {data|service|api}
```

示例：`/phase-contract 2 data`（Phase 2 数据层完成）

## 执行步骤

### Step 1：确认输入

读取以下文件建立提取基准：
- `PLAN.md`：确认本层任务范围和文件列表
- `docs/arch-review.md`：提取与本层相关的设计决策
- `docs/security-review.md`：提取与本层相关的安全约束
- `docs/api/{模块名}.md`：API 层专用，确认接口契约来源

### Step 2：扫描实现产物并提取内容

根据 `PLAN.md` 中本层的文件范围扫描已实现代码，结合 Step 1 的基准文件，提取签名 + 语义 + 约束来源。

**数据层（data）提取**：

```
实体定义：
- 字段名、类型、约束、是否可空、枚举值
- 约束来源（来自 arch-review / security-review，如 tenant_id 隔离要求）

Repository 接口：
- 方法签名（方法名、入参类型、返回类型）
- 业务语义（这个方法做什么、不做什么）
- 特殊约定（如所有查询方法必须携带 tenant_id 过滤）

与 arch-review 的差异（如有，说明原因）
```

**服务层（service）提取**：

分两个区块，供不同场景使用：

```
## 对外接口（跨模块可见）
- 方法签名（方法名、入参类型、返回值类型、受检异常）
- 业务语义（调用方需要知道的行为约定，如"返回空列表而不是抛异常"）
- 约束来源（来自哪条 arch-review / security-review 决策）

## 内部实现约定（仅本模块内部参考）
- 事务边界说明
- 外部系统调用约定（堡垒机接口调用方式、失败处理策略）
- 其他不对外暴露的实现细节
```

**API 层（api）提取**：

```
接口清单：
- 路径、HTTP 方法（对照 docs/api/*.md 确认一致性）
- 请求 DTO（字段名、类型、是否必填、校验规则）
- 响应 DTO（字段名、类型）
- 错误码（HTTP 状态码 + 业务错误码 + 含义）
- 鉴权方式

与 docs/api/*.md 的差异（如有，必须说明是否经过评审确认）
```

### Step 3：生成 contract 文件

输出路径：`docs/contracts/{模块名}-{layer}.md`

```markdown
# Contract: {模块名} - {技术层}

> Phase {N} | 生成时间：{date}
> Superpowers /review 通过确认

## 接口定义
{根据层类型填入 Step 2 对应内容}

## 与规划的差异
{实现与 arch-review.md 存在偏差时说明原因，无差异填"无"}

## 下一层注意事项
{下一技术层 brainstorming 时需要特别注意的约束，来自本层实现中发现的边界条件}
```

服务层的 contract 文件必须包含"对外接口"和"内部实现约定"两个明确章节，供 hook 按场景选择性注入。

### Step 4：提示下一步

**data 层完成后**：
```
docs/contracts/{模块}-data.md 已生成。
下一步：开始 Layer 2（服务层），执行 Superpowers /brainstorming。
brainstorming-pre hook 将自动注入 contract 文件。
```

**service 层完成后**：
```
docs/contracts/{模块}-service.md 已生成。
下一步：开始 Layer 3（API 层），执行 Superpowers /brainstorming。
注意：API 层必须严格遵循 docs/api/{模块名}.md，发现偏差停下来报告。
```

**api 层完成后**：
```
docs/contracts/{模块}-api.md 已生成。
所有技术层已完成，下一步执行 /phase-verify {N} 进行 Phase 验收。
```

## 注意事项

- contract 不修改 STATE.md，STATE 的唯一写入入口是 /phase-verify
- 业务语义和约束来源是必填项，不允许只记录签名而省略语义说明
- 服务层 contract 的两个章节分区是强制要求，影响跨模块 hook 注入的准确性
