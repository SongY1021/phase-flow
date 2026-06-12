#!/usr/bin/env node

/**
 * PhaseFlow 安装逻辑
 *
 * 三类文件，三种处理策略：
 * - CLAUDE.md         → 追加合并（保留项目原有内容，末尾追加 PhaseFlow 内容）
 * - settings.json     → 字段合并（只合并 hooks 字段，保留项目其他配置）
 * - hooks / skills    → 询问是否覆盖（或 --force 直接覆盖）
 */

const fs = require("fs");
const path = require("path");
const readline = require("readline");

// ─── 常量 ────────────────────────────────────────────────────────────────────

const TEMPLATE_DIR = path.join(__dirname, "..", "templates");
const PROJECT_MARKERS = [".git", "package.json", "pom.xml", "build.gradle", "go.mod", "Cargo.toml"];

// 需要特殊处理的文件（不走普通覆盖逻辑）
const MERGE_STRATEGIES = {
  "CLAUDE.md": "append",
  ".claude/settings.json": "merge-hooks",
};

// ─── 工具函数 ────────────────────────────────────────────────────────────────

function isProjectRoot(dir) {
  return PROJECT_MARKERS.some((marker) => fs.existsSync(path.join(dir, marker)));
}

function isGlobalInstall() {
  return process.env.npm_config_global === "true";
}

function relativePath(filePath, base) {
  return path.relative(base, filePath);
}

function prompt(question) {
  const rl = readline.createInterface({ input: process.stdin, output: process.stdout });
  return new Promise((resolve) => {
    rl.question(question, (answer) => {
      rl.close();
      resolve(answer.trim().toLowerCase());
    });
  });
}

// ─── 合并策略 ────────────────────────────────────────────────────────────────

/**
 * CLAUDE.md：追加合并
 * 在已有内容末尾追加分隔线 + PhaseFlow 内容
 * 如果已经包含 PhaseFlow 标记，跳过（幂等）
 */
function appendClaudeMd(srcPath, destPath, dryRun) {
  const PHASEFLOW_MARKER = "<!-- PhaseFlow -->";
  const srcContent = fs.readFileSync(srcPath, "utf-8");
  const destContent = fs.readFileSync(destPath, "utf-8");

  if (destContent.includes(PHASEFLOW_MARKER)) {
    console.log("   CLAUDE.md 已包含 PhaseFlow 内容，跳过");
    return "skipped";
  }

  if (!dryRun) {
    const separator = `\n\n---\n\n${PHASEFLOW_MARKER}\n`;
    fs.writeFileSync(destPath, destContent + separator + srcContent, "utf-8");
  }
  return "merged";
}

/**
 * settings.json：合并 hooks 字段
 * 读取已有 settings.json，把 PhaseFlow 的 hooks 合并进去
 * 已有的其他字段（permissions 等）完全保留
 * 如果某个 hook 事件已存在，把 PhaseFlow 的条目追加进去（不替换）
 */
function mergeSettingsJson(srcPath, destPath, dryRun) {
  let existing = {};
  let phaseflow = {};

  try {
    existing = JSON.parse(fs.readFileSync(destPath, "utf-8"));
  } catch {
    existing = {};
  }

  try {
    phaseflow = JSON.parse(fs.readFileSync(srcPath, "utf-8"));
  } catch {
    return "error";
  }

  const PHASEFLOW_MARKER = "__phaseflow__";

  // 检查是否已经合并过（幂等）
  const existingStr = JSON.stringify(existing);
  if (existingStr.includes(PHASEFLOW_MARKER)) {
    console.log("   .claude/settings.json 已包含 PhaseFlow hooks，跳过");
    return "skipped";
  }

  if (!dryRun) {
    const merged = { ...existing };

    if (!merged.hooks) {
      merged.hooks = {};
    }

    // 逐个事件类型合并
    for (const [event, hookGroups] of Object.entries(phaseflow.hooks || {})) {
      if (!merged.hooks[event]) {
        merged.hooks[event] = [];
      }
      // 给每个 hook 条目打上 PhaseFlow 标记，用于幂等检查
      const markedGroups = hookGroups.map((group) => ({
        ...group,
        [PHASEFLOW_MARKER]: true,
        hooks: group.hooks.map((h) => ({ ...h, [PHASEFLOW_MARKER]: true })),
      }));
      merged.hooks[event].push(...markedGroups);
    }

    fs.writeFileSync(destPath, JSON.stringify(merged, null, 2) + "\n", "utf-8");
  }
  return "merged";
}

// ─── 文件遍历 ────────────────────────────────────────────────────────────────

/**
 * 遍历 templates 目录，按文件类型分类
 */
function scanTemplates(templateDir, targetDir) {
  const results = {
    toCreate: [],    // 目标不存在，直接复制
    toMerge: [],     // 需要合并策略处理
    toConflict: [],  // 普通冲突，需用户确认
  };

  function walk(srcDir, destDir) {
    fs.mkdirSync(destDir, { recursive: true });

    for (const entry of fs.readdirSync(srcDir)) {
      const srcPath = path.join(srcDir, entry);
      const destPath = path.join(destDir, entry);
      const stat = fs.statSync(srcPath);

      if (stat.isDirectory()) {
        walk(srcPath, destPath);
        continue;
      }

      const rel = relativePath(destPath, targetDir);
      const strategy = MERGE_STRATEGIES[rel];

      if (!fs.existsSync(destPath)) {
        results.toCreate.push({ src: srcPath, dest: destPath, rel });
      } else if (strategy) {
        results.toMerge.push({ src: srcPath, dest: destPath, rel, strategy });
      } else {
        results.toConflict.push({ src: srcPath, dest: destPath, rel });
      }
    }
  }

  walk(templateDir, targetDir);
  return results;
}

// ─── 主流程 ──────────────────────────────────────────────────────────────────

async function install(targetDir, options = {}) {
  const { dryRun = false, force = false } = options;
  const cwd = targetDir || process.cwd();

  console.log("\n🚀 PhaseFlow 安装程序\n");

  // 1. 禁止全局安装
  if (isGlobalInstall()) {
    console.error("❌ PhaseFlow 不支持全局安装（npm install -g）");
    console.error("   请在项目根目录下使用本地安装：");
    console.error("   npm install --save-dev phase-flow");
    console.error("   或者使用 npx：npx phase-flow init");
    process.exit(1);
  }

  // 2. 校验项目根目录
  if (!isProjectRoot(cwd)) {
    console.error("❌ 当前目录不是有效的项目根目录");
    console.error(`   目录：${cwd}`);
    console.error(`   PhaseFlow 需要在包含以下文件之一的目录中安装：`);
    console.error(`   ${PROJECT_MARKERS.join("、")}`);
    console.error("\n   请在你的项目根目录下重新执行安装。");
    process.exit(1);
  }

  console.log(`📁 安装目标：${cwd}`);
  if (dryRun) console.log("   （dry-run 模式，不会写入任何文件）");
  console.log("");

  // 3. 扫描所有文件，分类
  const { toCreate, toMerge, toConflict } = scanTemplates(TEMPLATE_DIR, cwd);

  const stats = { created: 0, merged: 0, overwritten: 0, skipped: 0 };

  // 4. 直接创建新文件
  for (const { src, dest } of toCreate) {
    if (!dryRun) {
      fs.mkdirSync(path.dirname(dest), { recursive: true });
      fs.copyFileSync(src, dest);
    }
    stats.created++;
  }

  // 5. 合并策略处理（CLAUDE.md、settings.json）
  if (toMerge.length > 0) {
    console.log("📝 以下文件将进行合并（保留你的原有内容）：\n");
    for (const { src, dest, rel, strategy } of toMerge) {
      console.log(`   ${rel}`);
      let result = "skipped";
      if (strategy === "append") {
        console.log(`   └─ 策略：追加到已有 CLAUDE.md 末尾`);
        result = appendClaudeMd(src, dest, dryRun);
      } else if (strategy === "merge-hooks") {
        console.log(`   └─ 策略：合并 hooks 字段，保留其他配置`);
        result = mergeSettingsJson(src, dest, dryRun);
      }
      if (result === "merged") stats.merged++;
      else stats.skipped++;
    }
    console.log("");
  }

  // 6. 普通冲突文件处理（hooks / skills）
  if (toConflict.length > 0) {
    if (force) {
      console.log("⚠️  以下文件将被覆盖（--force 模式）：\n");
      for (const { src, dest, rel } of toConflict) {
        console.log(`   ${rel}`);
        if (!dryRun) {
          fs.mkdirSync(path.dirname(dest), { recursive: true });
          fs.copyFileSync(src, dest);
        }
        stats.overwritten++;
      }
      console.log("");
    } else {
      console.log("⚠️  以下文件已存在，是否覆盖？\n");
      for (const { src, dest, rel } of toConflict) {
        const answer = await prompt(`   ${rel}\n   覆盖？[y/N] `);
        if (answer === "y" || answer === "yes") {
          if (!dryRun) {
            fs.mkdirSync(path.dirname(dest), { recursive: true });
            fs.copyFileSync(src, dest);
          }
          stats.overwritten++;
        } else {
          console.log(`   跳过`);
          stats.skipped++;
        }
      }
      console.log("");
    }
  }

  // 7. 输出结果
  console.log("─".repeat(50));
  console.log(`✅ PhaseFlow 安装完成\n`);
  if (!dryRun) {
    console.log(`   新建文件：${stats.created} 个`);
    if (stats.merged > 0)     console.log(`   合并文件：${stats.merged} 个（原有内容已保留）`);
    if (stats.overwritten > 0) console.log(`   覆盖文件：${stats.overwritten} 个`);
    if (stats.skipped > 0)    console.log(`   跳过文件：${stats.skipped} 个`);
  }
  console.log("");
  console.log("📋 已安装内容：");
  console.log("   .claude/settings.json        ← Hooks 配置（已合并）");
  console.log("   .claude/hooks/               ← SessionStart / SessionEnd / brainstorming-pre");
  console.log("   .claude/skills/              ← phase-split / plan / contract / handoff / verify");
  console.log("   CLAUDE.md                    ← 框架分工与执行规则（已追加）");
  console.log("");
  console.log("🎯 快速开始：");
  console.log("   1. 完成 gstack 决策阶段（arch-review + security-review + API 文档）");
  console.log("   2. 执行 /phase-split 生成 ROADMAP.md");
  console.log("   3. 执行 /phase-plan 1 开始第一个 Phase");
  console.log("");
  console.log("📖 完整文档：https://github.com/SongY1021/phase-flow");
  console.log("─".repeat(50));
}

module.exports = { install };
