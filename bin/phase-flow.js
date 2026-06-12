#!/usr/bin/env node

/**
 * PhaseFlow CLI 入口
 *
 * 支持的命令：
 *   phase-flow init            ← 安装到当前项目目录
 *   phase-flow init --force    ← 强制覆盖已存在的文件
 *   phase-flow init --dry-run  ← 预览安装内容，不写入文件
 *   phase-flow --version       ← 查看版本
 *   phase-flow --help          ← 查看帮助
 */

const { install } = require("../src/install");
const pkg = require("../package.json");

const args = process.argv.slice(2);
const command = args[0];
const flags = {
  force: args.includes("--force"),
  dryRun: args.includes("--dry-run"),
  help: args.includes("--help") || args.includes("-h"),
  version: args.includes("--version") || args.includes("-v"),
};

// ─── 帮助文本 ─────────────────────────────────────────────────────────────────

function printHelp() {
  console.log(`
PhaseFlow v${pkg.version}
Claude Code 流程驱动开发的 Skills & Hooks 工具集

用法：
  npx phase-flow init             安装到当前项目目录
  npx phase-flow init --force     强制覆盖已存在的文件
  npx phase-flow init --dry-run   预览安装内容，不写入文件

选项：
  --force     跳过冲突确认，直接覆盖所有已存在文件
  --dry-run   预览模式，仅显示将要安装的内容
  --version   显示版本号
  --help      显示帮助信息

注意事项：
  · PhaseFlow 只能在项目根目录下安装（需包含 .git 或 package.json）
  · 不支持全局安装（npm install -g）
  · 安装内容写入当前目录的 .claude/ 和 CLAUDE.md，不影响全局配置

文档：https://github.com/SongY1021/phase-flow
`);
}

// ─── 主入口 ──────────────────────────────────────────────────────────────────

async function main() {
  if (flags.version) {
    console.log(`phase-flow v${pkg.version}`);
    process.exit(0);
  }

  if (flags.help || !command) {
    printHelp();
    process.exit(0);
  }

  if (command === "init") {
    await install(process.cwd(), {
      force: flags.force,
      dryRun: flags.dryRun,
    });
    process.exit(0);
  }

  console.error(`❌ 未知命令：${command}`);
  console.error(`   执行 phase-flow --help 查看可用命令`);
  process.exit(1);
}

main().catch((err) => {
  console.error(`\n❌ 安装失败：${err.message}`);
  process.exit(1);
});
