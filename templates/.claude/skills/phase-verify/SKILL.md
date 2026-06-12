---
name: phase-verify
description: 【PhaseFlow】当一个 Phase 的所有技术层（数据层/服务层/API层）全部完成后，执行 Phase 级别的需求完整性验收，通过后原子更新 STATE.md。STATE.md 的唯一写入入口。在 Phase 所有层的 contract 均已生成后触发。用户说"验收 Phase N"、"Phase 完成了"、"phase-verify"时使用此工具。
---

# PhaseFlow — phase-verify

执行 Phase 级别的需求完整性验收，通过后原子更新状态，驱动项目推进到下一个 Phase。

## 核心定位

**STATE.md 的唯一写入入口**，contract 和 hook 均不修改 STATE。

与 Superpowers `/review` 的分工：
- **Superpowers /review**：代码质量审查（命名规范、边界条件、竞态条件），每个技术层完成后执行
- **/phase-verify**：需求完整性验收（ROADMAP 验收标准是否全部达成），整个 Phase 完成后执行

两者都不能省，顺序是 Superpowers /review 在前，/phase-verify 在后。

## 前置条件

执行前确认：
- `PLAN.md` 中三个技术层均已完成
- `docs/contracts/{模块}-data.md` 存在
- `docs/contracts/{模块}-service.md` 存在
- `docs/contracts/{模块}-api.md` 存在
- 所有技术层的 Superpowers `/review` 均已通过

如有未满足项，停止并告知用户。

## 使用方式

```
/phase-verify {N}
```

## 执行步骤

### Step 1：读取验收基准

读取以下文件，建立验收检查项：
1. `ROADMAP.md` → Phase N 的验收标准（最终判定依据）
2. `docs/api/{模块名}.md` → 规划期接口契约
3. `docs/contracts/{模块}-api.md` → 实际实现的接口
4. `docs/contracts/{模块}-service.md` → 服务层实现
5. `docs/contracts/{模块}-data.md` → 数据层实现
6. `docs/security-review.md` → 本模块相关安全约束

### Step 2：执行三项验收检查

**检查 1：需求完整性**

逐条核对 ROADMAP.md 中 Phase N 的验收标准，对照三份 contract 文件确认每条是否有对应实现。

**检查 2：接口一致性**

对照 `docs/api/{模块名}.md` 与 `docs/contracts/{模块}-api.md`，检查：
- 接口路径和方法是否一致
- 请求/响应结构是否一致
- 错误码是否一致
- 如有差异，contract 中是否有经过评审确认的说明

**检查 3：安全约束落实**

对照 `docs/security-review.md`，逐条确认本模块安全约束已在 contract 中体现：
- tenant_id 隔离是否在数据层和服务层均有记录
- 鉴权方式是否正确集成
- 其他本模块特有的安全要求

### Step 3：输出验收报告

**验收通过时**：

```markdown
## Phase {N} 验收报告

**结论：通过 ✅**
验收时间：{date}

### 需求完整性
- ✅ {验收标准 1}
- ✅ {验收标准 2}

### 接口一致性
- ✅ 接口路径和方法与文档一致
- ✅ 请求/响应结构与文档一致
- ✅ 错误码与文档一致

### 安全约束
- ✅ {安全约束 1}
- ✅ {安全约束 2}
```

**验收不通过时**：

```markdown
## Phase {N} 验收报告

**结论：未通过 ❌**

### 缺失项
- ❌ {具体缺失项，说明对应哪条验收标准}
- ❌ {接口不一致项，说明差异内容}

STATE.md 不会更新，请修复以上问题后重新执行 /phase-verify {N}。
```

验收不通过时，**立即停止，不执行 Step 4**。

### Step 4：原子更新 STATE.md（仅验收通过后执行）

扫描 `docs/contracts/` 目录，确认当前模块三层 contract 均存在后，一次性完成以下全部更新：

1. Phase N 状态：`in_progress` → `completed`
2. Phase N+1 状态：`pending` → `in_progress`（如存在且无未完成的前置依赖）
3. `Current Phase`：更新为 N+1
4. `Current Layer`：清空（等待 /phase-plan 填入）
5. `Last Updated`：更新为当前时间戳

**并行 Phase 的处理**：如果 ROADMAP 中标记下一个可并行的 Phase，同时将其状态更新为 `in_progress`，并在 STATE.md 中注明。

### Step 5：提示下一步

```
Phase {N} 验收通过，STATE.md 已更新。

下一步：
  执行 /phase-plan {N+1} 开始 Phase {N+1}：{模块名}
```

如果 Phase N 是最后一个 Phase：

```
Phase {N} 验收通过，所有 Phase 已完成。

下一步：进入集成验收阶段
  - 读取所有 docs/contracts/ 文件
  - 执行 gstack /review（全量代码审查）
  - 执行 gstack /qa（端到端测试）
  - 执行 gstack /cso（安全验收）
```
