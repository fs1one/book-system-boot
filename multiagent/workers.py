# -*- coding: utf-8 -*-
"""producer 适配层。

真实适配：调用 CodeBuddy Code CLI 的 headless 模式，在隔离 worktree 内改文件。
模拟适配：复制预置产物目录，用于在没有 CodeBuddy 的机器上验证整条流水线。

两者返回同一个结构，编排器不关心是谁干的：
    {"worker": str, "files": list[str], "note": str, "version": str|None}
"""
from __future__ import annotations

import json
import re
import shutil
import subprocess
from pathlib import Path


class WorkerError(RuntimeError):
    """producer 无法完成本次产出。"""


def produce(cfg: dict, spec: dict, worktree: Path, round_no: int,
            feedback: dict | None, runtime: Path, root: Path) -> dict:
    mode = cfg["producer"]["mode"]
    if mode == "codebuddy":
        try:
            return _codebuddy(cfg, spec, worktree, round_no, feedback, runtime)
        except WorkerError as exc:
            if not cfg["producer"].get("allow_fallback", False):
                raise
            # 真适配器可能留下了半成品，降级前先回到干净状态，避免把残骸提交进去。
            _reset_worktree(worktree)
            try:
                res = _mock(cfg, spec, worktree, round_no, root)
            except WorkerError as mock_exc:
                raise WorkerError(f"{exc}；且 mock 也不可用（{mock_exc}）") from exc
            res["note"] = f"CodeBuddy 不可用（{exc}），已降级为 mock producer"
            return res
    return _mock(cfg, spec, worktree, round_no, root)


def _mock(cfg: dict, spec: dict, worktree: Path, round_no: int, root: Path) -> dict:
    # 按任务隔离：demo/mock/<task-id>/roundN，避免不同任务串用同一份预置产物
    src = root / cfg["demo"]["mock_dir"] / spec["id"] / f"round{round_no}"
    if not src.exists():
        raise WorkerError(f"mock 缺少任务 {spec['id']} 的 round{round_no} 产物：{src}")

    files: list[str] = []
    for f in sorted(src.rglob("*")):
        if not f.is_file():
            continue
        rel = f.relative_to(src)
        dst = worktree / rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(f, dst)
        files.append(rel.as_posix())

    return {"worker": "mock", "files": files, "version": None,
            "note": f"复制 round{round_no} 预置产物（{len(files)} 个文件）"}


def _codebuddy(cfg: dict, spec: dict, worktree: Path, round_no: int,
               feedback: dict | None, runtime: Path) -> dict:
    cb = cfg["producer"]["codebuddy"]
    version = _probe(cb.get("version_cmd"))

    prompt_text = _render_prompt(spec, feedback, worktree)
    prompt_path = runtime / "artifacts" / f"{spec['id']}-r{round_no}-prompt.md"
    prompt_path.parent.mkdir(parents=True, exist_ok=True)
    prompt_path.write_text(prompt_text, encoding="utf-8")

    # 支持两种占位：{prompt} 直接把提示词塞进 argv（-p 的正统用法），
    # {prompt_file} 传路径（适合超长提示词或需要留档的场景）。
    rendered = [
        str(part).replace("{prompt_file}", str(prompt_path)).replace("{prompt}", prompt_text)
        for part in cb["cmd"][1:]
    ]
    prefix, bin_display = _resolve_launcher(cb["cmd"][0])
    cmd = [*prefix, *rendered]

    display = [bin_display, *[
        str(part).replace("{prompt_file}", prompt_path.name)
        .replace("{prompt}", f"<prompt {len(prompt_text)} chars>")
        for part in cb["cmd"][1:]
    ]]
    try:
        p = subprocess.run(
            cmd,
            cwd=str(worktree),
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=cb.get("timeout_sec", 900),
        )
    except FileNotFoundError:
        raise WorkerError(f"未找到可执行文件 {cmd[0]}，请先安装 CodeBuddy Code CLI")
    except subprocess.TimeoutExpired:
        raise WorkerError(f"CodeBuddy 超时（>{cb.get('timeout_sec', 900)}s）")

    log_path = runtime / "artifacts" / f"{spec['id']}-r{round_no}-producer.log"
    log_path.write_text(
        f"$ {' '.join(display)}\n\n[stdout]\n{p.stdout}\n\n[stderr]\n{p.stderr}"
        f"\n\n[prompt]\n{prompt_text}",
        encoding="utf-8",
    )
    if p.returncode != 0:
        raise WorkerError(f"CodeBuddy 退出码 {p.returncode}，详见 {log_path.name}")

    changed = _git_status(worktree)
    if not changed:
        raise WorkerError("CodeBuddy 退出码为 0 但没有任何文件改动（检查权限模式 / cwd / 提示词）")

    return {"worker": "codebuddy", "files": changed, "version": version,
            "note": f"headless 退出码 0，改动 {len(changed)} 个文件，日志 {log_path.name}"}


def _reset_worktree(worktree: Path) -> None:
    for cmd in (["git", "checkout", "--", "."], ["git", "clean", "-fd"]):
        subprocess.run(cmd, cwd=str(worktree), capture_output=True, text=True)


def _resolve_launcher(bin_name: str) -> tuple[list[str], str]:
    """把 `codebuddy` 解析成可直接 spawn 的 argv 前缀。

    Windows 上 npm 全局安装出来的是 `codebuddy.cmd` 批处理 shim，subprocess 无法直接执行，
    走 `cmd /c` 又会被多行中文提示词的引号规则弄坏。这里解析 shim 找到真正的 JS 入口，
    用 node 直接跑，argv 原样传递、不经过 cmd.exe。
    """
    found = shutil.which(bin_name)
    if not found:
        raise WorkerError(f"未找到可执行文件 {bin_name}，请先安装 CodeBuddy Code CLI")

    path = Path(found)
    if path.suffix.lower() in (".cmd", ".bat"):
        js = _shim_entry(path)
        if not js:
            raise WorkerError(f"{path.name} 是批处理 shim，但没定位到 JS 入口；请确认 node 在 PATH 上")
        node = shutil.which("node") or "node"
        return [node, str(js)], f"{bin_name} -> node {js.name}"

    return [str(path)], str(path)


def _shim_entry(cmd_path: Path) -> Path | None:
    """从 npm 的 .cmd shim 反查它包裹的 cli.js。"""
    base = cmd_path.parent
    pkg = base / "node_modules" / "@tencent-ai" / "codebuddy-code"
    pkg_json = pkg / "package.json"
    if pkg_json.exists():
        try:
            data = json.loads(pkg_json.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            data = {}
        bin_field = data.get("bin")
        rel = None
        if isinstance(bin_field, str):
            rel = bin_field
        elif isinstance(bin_field, dict):
            rel = bin_field.get("codebuddy") or next(iter(bin_field.values()), None)
        if rel:
            js = (pkg / rel).resolve()
            if js.exists():
                return js

    text = cmd_path.read_text(encoding="utf-8", errors="replace")
    match = re.search(r'%dp0%\\([^"]+?\.js)', text)
    if match:
        js = (base / match.group(1).replace("\\", "/")).resolve()
        if js.exists():
            return js
    return None


def _probe(version_cmd: list[str] | None) -> str | None:
    if not version_cmd:
        return None
    prefix, _ = _resolve_launcher(version_cmd[0])
    p = subprocess.run(
        [*prefix, *version_cmd[1:]], capture_output=True, text=True,
        encoding="utf-8", errors="replace", timeout=30,
    )
    text = (p.stdout or p.stderr or "").strip()
    return text.splitlines()[0][:120] if text else "unknown"


def _git_status(worktree: Path) -> list[str]:
    p = subprocess.run(
        ["git", "status", "--porcelain"], cwd=str(worktree),
        capture_output=True, text=True, encoding="utf-8", errors="replace",
    )
    files: list[str] = []
    for line in (p.stdout or "").splitlines():
        if len(line) < 4:
            continue
        path = line[3:].strip().strip('"')
        if " -> " in path:  # 重命名
            path = path.split(" -> ", 1)[1]
        files.append(path)
    return files


def _render_prompt(spec: dict, feedback: dict | None, worktree: Path) -> str:
    lines = [
        "# 编码任务",
        "",
        f"## 目标\n{spec['title']}",
        "",
        f"## 背景\n{spec.get('background', '（无）')}",
        "",
        f"## 工作目录\n`{worktree}`\n只允许在该目录内改动文件。",
        "",
        "## 允许修改",
        *[f"- {g}" for g in spec.get("owner_globs", [])],
        "",
        "## 禁止修改（验收测试已冻结）",
        *[f"- {g}" for g in spec.get("forbidden_globs", [])],
        "",
        "## 验收标准",
        *[f"{i + 1}. {a}" for i, a in enumerate(spec.get("acceptance", []))],
        "",
    ]
    if feedback:
        lines += [
            "## 上一轮未通过的检查（只修这些，不要顺手重构）",
            "```json",
            json.dumps(feedback, ensure_ascii=False, indent=2),
            "```",
            "",
        ]
    lines += [
        "## 交付要求",
        "- 直接修改工作目录中的文件；**不要执行 git commit**，提交由编排器负责。",
        "- 当前会话**没有 Bash / 终端工具**，不要尝试执行命令或跑测试；验证由编排器负责。",
        "- 不要新增第三方依赖，不要修改 package.json / 测试文件。",
        "- 不要输出大段解释，最后用 3 行内说明：改了什么、为什么、有什么风险。",
    ]
    return "\n".join(lines)
