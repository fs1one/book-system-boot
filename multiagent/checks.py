# -*- coding: utf-8 -*-
"""确定性检查：流水线里「机器可判」的部分，全部由 DSH 侧执行。

设计原则：产出方（producer）不参与判定，判定标准在任务契约里预先冻结。
每项检查返回 {id, title, status, detail}，status ∈ {pass, fail, skip}。
"""
from __future__ import annotations

import fnmatch
import os
import re
import shutil
import subprocess
from pathlib import Path

# 只抓「高置信度」的凭据形态，避免把普通文案误报成泄密。
SECRET_RE = re.compile(
    r"(sk-[A-Za-z0-9]{16,}"
    r"|AKID[A-Za-z0-9]{13,}"
    r"|BEGIN [A-Z ]*PRIVATE KEY"
    r"|password\s*[:=]\s*\S+)",
    re.IGNORECASE,
)


def _git(args: list[str], cwd: Path) -> str:
    p = subprocess.run(
        ["git", *args],
        cwd=str(cwd),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    return p.stdout or ""


def check_changed_nonempty(changed: list[str]) -> dict:
    if changed:
        return {"id": "changed", "title": "存在改动", "status": "pass",
                "detail": f"{len(changed)} 个文件"}
    return {"id": "changed", "title": "存在改动", "status": "fail",
            "detail": "producer 没有产生任何改动"}


def check_scope(changed: list[str], spec: dict, allow: list[str] | None = None) -> dict:
    """allow：额外放行的路径（CI 门禁里放行 planner_seed 的冻结测试）。"""
    allowed = list(spec.get("owner_globs", [])) + list(allow or [])
    forbidden = spec.get("forbidden_globs", [])
    outside = [f for f in changed if not any(fnmatch.fnmatch(f, g) for g in allowed)]
    hit = [f for f in changed
           if any(fnmatch.fnmatch(f, g) for g in forbidden) and f not in (allow or [])]
    if outside or hit:
        return {"id": "scope", "title": "改动范围", "status": "fail",
                "detail": f"越界={outside or '无'}；命中禁区={hit or '无'}"}
    return {"id": "scope", "title": "改动范围", "status": "pass",
            "detail": f"{len(changed)} 个文件均在允许范围内"}


def _spawn(cmd: list[str], cwd: Path, timeout: int) -> subprocess.CompletedProcess:
    """执行测试命令。

    Windows 上 `mvn` / `npm` 解析到的是 `.cmd` 批处理，subprocess 不能直接执行，
    必须交给 cmd.exe；Linux/macOS 或原生 exe 则直接 spawn。
    """
    exe = shutil.which(cmd[0]) or cmd[0]
    argv = [exe, *cmd[1:]]
    if os.name == "nt" and str(exe).lower().endswith((".cmd", ".bat")):
        argv = ["cmd", "/c", *argv]
    return subprocess.run(
        argv, cwd=str(cwd), capture_output=True, text=True,
        encoding="utf-8", errors="replace", timeout=timeout,
    )


def check_tests(cfg_checks: dict, worktree: Path) -> dict:
    cmd = cfg_checks.get("test_cmd", ["node", "--test"])
    try:
        p = _spawn(cmd, worktree, cfg_checks.get("timeout_sec", 120))
    except FileNotFoundError:
        return {"id": "tests", "title": "验收测试", "status": "fail",
                "detail": f"找不到命令 {cmd[0]}"}
    except subprocess.TimeoutExpired:
        return {"id": "tests", "title": "验收测试", "status": "fail",
                "detail": f"测试超时（>{cfg_checks.get('timeout_sec', 120)}s）"}

    out = (p.stdout or "") + "\n" + (p.stderr or "")
    # node --test 在管道下输出 TAP（# pass 8），在 TTY 下输出 spec（ℹ pass 8），两种都兼容。
    m_pass = re.search(r"(?:#|\u2139)\s*pass\s+(\d+)", out)
    m_fail = re.search(r"(?:#|\u2139)\s*fail\s+(\d+)", out)
    n_pass = int(m_pass.group(1)) if m_pass else -1
    n_fail = int(m_fail.group(1)) if m_fail else -1
    # 非 Node 栈（mvn / pytest / go test）没有 TAP 摘要，此时以退出码为准。
    ok = p.returncode == 0 and n_fail <= 0

    if n_pass == -1 and n_fail == -1:
        detail = f"exit={p.returncode}（无 TAP 摘要，按退出码判定）"
    else:
        detail = f"pass={n_pass} fail={n_fail} exit={p.returncode}"
    if not ok:
        bad = [ln.strip() for ln in out.splitlines()
               if ln.strip().startswith("not ok") or "AssertionError" in ln
               or "FAIL" in ln or "ERROR" in ln]
        if bad:
            detail += " | " + " / ".join(bad[:4])
    return {"id": "tests", "title": "验收测试", "status": "pass" if ok else "fail",
            "detail": detail[:500]}


def check_secrets(diff_text: str) -> dict:
    added = [ln for ln in diff_text.splitlines()
             if ln.startswith("+") and not ln.startswith("+++")]
    hits: list[str] = []
    for ln in added:
        m = SECRET_RE.search(ln)
        if m:
            hits.append(m.group(0)[:32])
    if hits:
        return {"id": "secrets", "title": "密钥/凭据扫描", "status": "fail",
                "detail": f"疑似泄露 {len(hits)} 处：{hits[:3]}"}
    return {"id": "secrets", "title": "密钥/凭据扫描", "status": "pass",
            "detail": f"扫描 {len(added)} 行新增内容，未命中凭据特征"}


def check_ui_contract(cfg_checks: dict, worktree: Path) -> dict:
    rel = cfg_checks.get("ui_file")
    if not rel:
        return {"id": "ui", "title": "UI 契约", "status": "skip", "detail": "未配置"}
    f = worktree / rel
    if not f.exists():
        return {"id": "ui", "title": "UI 契约", "status": "fail", "detail": f"缺少 {rel}"}
    text = f.read_text(encoding="utf-8", errors="replace")
    missing = [m for m in cfg_checks.get("ui_required_markers", []) if m not in text]
    if missing:
        return {"id": "ui", "title": "UI 契约", "status": "fail",
                "detail": f"{rel} 缺少标记：{missing}"}
    return {"id": "ui", "title": "UI 契约", "status": "pass",
            "detail": f"{rel} 满足 {len(cfg_checks.get('ui_required_markers', []))} 个契约标记"}


def check_diff_size(diff_text: str, limit: int) -> dict:
    changed = sum(
        1 for ln in diff_text.splitlines()
        if (ln.startswith("+") or ln.startswith("-"))
        and not ln.startswith("+++") and not ln.startswith("---")
    )
    if changed > limit:
        return {"id": "size", "title": "改动体积", "status": "fail",
                "detail": f"{changed} 行 > 上限 {limit} 行，要求拆分为更小的任务"}
    return {"id": "size", "title": "改动体积", "status": "pass",
            "detail": f"{changed} 行（上限 {limit}）"}


def _normalize_bytes(data: bytes) -> bytes:
    """比较内容而不是比较工作区的换行风格：Windows 上 core.autocrlf 会把 LF 转成 CRLF。"""
    return data.replace(b"\r\n", b"\n")


def check_frozen(seed_dir: Path | None, worktree: Path) -> dict:
    """冻结测试完整性：CI 上比路径白名单更强的一道门。

    管线里 producer 的 diff 本来就不含 test/（seed 提交在 diff_base 之前），
    但 CI 拿到的是整个 PR 范围，必须逐字节比对，防止「顺手把测试改了」。
    """
    if seed_dir is None or not seed_dir.is_dir():
        return {"id": "frozen", "title": "冻结测试完整性", "status": "skip",
                "detail": "任务未配置 planner_seed"}

    files = [f for f in sorted(seed_dir.rglob("*")) if f.is_file()]
    missing: list[str] = []
    drift: list[str] = []
    for src in files:
        rel = src.relative_to(seed_dir)
        dst = worktree / rel
        if not dst.exists():
            missing.append(rel.as_posix())
        elif _normalize_bytes(dst.read_bytes()) != _normalize_bytes(src.read_bytes()):
            drift.append(rel.as_posix())

    if missing or drift:
        return {"id": "frozen", "title": "冻结测试完整性", "status": "fail",
                "detail": f"缺失={missing or '无'}；被改动={drift or '无'}"}
    return {"id": "frozen", "title": "冻结测试完整性", "status": "pass",
            "detail": f"{len(files)} 个冻结文件与任务契约逐字节一致"}


def run_gate(cfg: dict, repo: Path, spec: dict, base: str,
             seed_dir: Path | None = None) -> list[dict]:
    """CI 门禁：在任意 checkout 上跑确定性检查，不依赖 CodeBuddy / 网络 / 积分。"""
    cfg_checks = cfg["checks"]
    diff_text = _git(["diff", f"{base}..HEAD"], repo)
    changed = [ln.strip() for ln in
               _git(["diff", "--name-only", f"{base}..HEAD"], repo).splitlines()
               if ln.strip()]
    seed_files = ([f.relative_to(seed_dir).as_posix() for f in seed_dir.rglob("*") if f.is_file()]
                  if seed_dir and seed_dir.is_dir() else [])

    return [
        check_frozen(seed_dir, repo),
        check_changed_nonempty(changed),
        check_scope(changed, spec, allow=seed_files),
        check_tests(cfg_checks, repo),
        check_secrets(diff_text),
        check_ui_contract(cfg_checks, repo),
        check_diff_size(diff_text, cfg_checks.get("max_diff_lines", 400)),
    ]


def run_all(cfg: dict, worktree: Path, spec: dict, base_commit: str) -> list[dict]:
    cfg_checks = cfg["checks"]
    diff_text = _git(["diff", f"{base_commit}..HEAD"], worktree)
    changed = [ln.strip() for ln in
               _git(["diff", "--name-only", f"{base_commit}..HEAD"], worktree).splitlines()
               if ln.strip()]

    return [
        check_changed_nonempty(changed),
        check_scope(changed, spec),
        check_tests(cfg_checks, worktree),
        check_secrets(diff_text),
        check_ui_contract(cfg_checks, worktree),
        check_diff_size(diff_text, cfg_checks.get("max_diff_lines", 400)),
    ]
