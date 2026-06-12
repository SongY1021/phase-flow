#!/usr/bin/env node

/**
 * PhaseFlow 安装逻辑
 *
 * 职责：
 * 1. 校验当前目录是否为合法项目根目录
 * 2. 把 templates/ 下的所有文件复制到当前项目目录
 * 3. 已存在的文件提示用户确认是否覆盖
 */

const fs = require("fs");
const path = require("path");
const readline = require("readline");

// ─── 常量 ────────────────────────────────────────────────────────────────────

const TEMPLATE_DIR = path.join(__dirname, "..", "templates");
const PROJECT_MARKERS = [".git", "package.json", "pom.xml", "build.gradle", "go.mod", "Cargo.toml"];

// ─── 工具函数 ────────────────────────────────────────────────────────────────

function isProjectRoot(dir) {
  return PROJECT_MARKERS.some((marker) => fs.existsSync(path.join(dir, marker)));
}

function isGlobalInstall() {
  // npm install -g 时，npm_config_global 为 'true'
  return process.env.npm_config_global === "true";
}

function copyDirRecursive(src, dest, dryRun = false) {
  const results = { copied: [], skipped: [], conflicts: [] };

  function walk(srcDir, destDir) {
    fs.mkdirSync(destDir, { recursive: true });

    for (const entry of fs.readdirSync(srcDir)) {
      const srcPath = path.join(srcDir, entry);
      const destPath = path.join(destDir, entry);
      const stat = fs.statSync(srcPath);

      if (stat.isDirectory()) {
        walk(srcPath, destPath);
      } else {
        if (fs.existsSync(destPath)) {
          results.conflicts.push(destPath);
        } else {
          if (!dryRun) {
            fs.copyFileSync(srcPath, destPath);
          }
          results.copied.push(destPath);
        }
      }
    }
  }

  walk(src, dest);
  return results;
}

function overwriteFile(src, dest) {
  fs.mkdirSync(path.dirname(dest), { recursive: true });
  fs.copyFileSync(src, dest);
}

function relativePath(filePath, base) {
  return path.relative(base, filePath);
}

function prompt(question) {
  const rl = readline.createInterface({
    input: process.stdin,
    output: process.stdout,
  });
  return new Promise((resolve) => {
    rl.question(question, (answer) => {
      rl.close();
      resolve(answer.trim().toLowerCase());
    });
  });
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
    console.error("   或者使用 npx：");
    console.error("   npx phase-flow init");
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

  if (dryRun) {
    console.log("   （dry-run 模式，不会写入任何文件）\n");
  }

  // 3. 复制文件，检测冲突
  const { copied, conflicts } = copyDirRecursive(TEMPLATE_DIR, cwd, true); // 先 dry-run 探测

  // 4. 处理冲突文件
  const toOverwrite = [];

  if (conflicts.length > 0) {
    if (force) {
      // --force 模式直接全部覆盖
      toOverwrite.push(...conflicts);
      console.log(`⚠️  以下文件将被覆盖（--force 模式）：`);
      conflicts.forEach((f) => console.log(`   ${relativePath(f, cwd)}`));
      console.log("");
    } else {
      console.log("⚠️  以下文件已存在，请选择处理方式：\n");
      for (const conflictPath of conflicts) {
        const rel = relativePath(conflictPath, cwd);
        const answer = await prompt(`   ${rel}\n   覆盖？[y/N] `);
        if (answer === "y" || answer === "yes") {
          toOverwrite.push(conflictPath);
        } else {
          console.log(`   跳过 ${rel}`);
        }
      }
      console.log("");
    }
  }

  // 5. 执行实际写入
  if (!dryRun) {
    // 复制无冲突的新文件
    copyDirRecursive(TEMPLATE_DIR, cwd, false);

    // 覆盖用户确认的冲突文件
    for (const destPath of toOverwrite) {
      const relativeToDest = path.relative(cwd, destPath);
      const srcPath = path.join(TEMPLATE_DIR, relativeToDest);
      if (fs.existsSync(srcPath)) {
        overwriteFile(srcPath, destPath);
      }
    }
  }

  // 6. 输出结果
  const totalCopied = copied.length + toOverwrite.length;
  const totalSkipped = conflicts.length - toOverwrite.length;

  console.log("─".repeat(50));
  console.log(`✅ PhaseFlow 安装完成\n`);
  console.log(`   复制文件：${dryRun ? "(dry-run)" : totalCopied} 个`);
  if (totalSkipped > 0) {
    console.log(`   跳过文件：${totalSkipped} 个`);
  }
  console.log("");
  console.log("📋 已安装内容：");
  console.log("   .claude/settings.json        ← Hooks 配置");
  console.log("   .claude/hooks/               ← SessionStart / SessionEnd / brainstorming-pre");
  console.log("   .claude/skills/              ← phase-split / plan / contract / handoff / verify");
  console.log("   CLAUDE.md                    ← 框架分工与执行规则");
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
