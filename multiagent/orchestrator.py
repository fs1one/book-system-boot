#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""CodeBuddy x DSH 多 Agent 流水线编排器。

角色分工（按各自长处分，而不是按功能清单分）
-------------------------------------------
planner    (DSH)       读仓库、产出任务契约、**先写验收测试并冻结**
producer   (CodeBuddy) 在隔离 worktree 内实现功能与 UI，单写者，只碰 owner_globs
verifier   (DSH)       确定性检查（测试/范围/凭据/UI 契约/体积）+ 判断性评审
integrator (DSH)       仅在 PASS 后合并，写 co-author trailer 与审计账本

三条硬约束
----------
1. 单一写者：同一任务同一时刻只有一个 producer 持有 lock。
2. git 是唯一事实源：回滚权威是 commit，不依赖任何一方的会话级 checkpoint。
3. 交接只走文件契约（JSON）：两个 agent 不实时对话，避免互相污染上下文。

用法
----
    python orchestrator.py bootstrap
    python orchestrator.py run --task demo/specs/pricing-discount-tier.json
    python orchestrator.py resume --task-id pricing-discount-tier
    python orchestrator.py status --task-id pricing-discount-tier

退出码：0 完成 / 3 等待评审 / 1 失败
"""
from __future__ import annotations

import argparse
import copy
import json
import os
import shutil
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

import checks as checks_mod
import workers

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parent
# utf-8-sig：Windows 记事本/PowerShell 保存的 JSON 常带 BOM，不能因此拒绝启动。
BASE_CFG = json.loads((ROOT / "config.json").read_text(encoding="utf-8-sig"))
PROJECT = (ROOT / BASE_CFG["project_dir"]).resolve()
RUNTIME = ROOT / ".multiagent"

for _sub in ("state", "handoffs", "artifacts", "locks", "reports"):
    (RUNTIME / _sub).mkdir(parents=True, exist_ok=True)


# --------------------------------------------------------------------------- 基础工具

def now_iso() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


def write_json(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def read_json(path: Path) -> dict:
    # utf-8-sig 同时兼容带 BOM / 不带 BOM 的文件（任务契约、裁决、状态都可能被手工编辑）。
    return json.loads(path.read_text(encoding="utf-8-sig"))


def sh(args: list[str], cwd: Path | None = None, timeout: int = 120,
       check: bool = True) -> subprocess.CompletedProcess:
    try:
        p = subprocess.run(
            args, cwd=str(cwd) if cwd else None, capture_output=True, text=True,
            encoding="utf-8", errors="replace", timeout=timeout,
        )
    except FileNotFoundError:
        raise RuntimeError(f"命令不存在：{args[0]}")
    except subprocess.TimeoutExpired:
        raise RuntimeError(f"命令超时（>{timeout}s）：{' '.join(map(str, args))}")
    if check and p.returncode != 0:
        raise RuntimeError(
            f"命令失败({p.returncode})：{' '.join(map(str, args))}\n"
            f"stdout: {(p.stdout or '')[-1500:]}\nstderr: {(p.stderr or '')[-1500:]}"
        )
    return p


def git(args: list[str], cwd: Path | None = None, check: bool = True) -> subprocess.CompletedProcess:
    return sh(["git", *args], cwd=cwd or PROJECT, check=check)


def git_out(args: list[str], cwd: Path | None = None) -> str:
    return (git(args, cwd=cwd).stdout or "").strip()


def ledger(**event) -> None:
    record = {"ts": now_iso(), **event}
    with (RUNTIME / "ledger.jsonl").open("a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")
    phase = str(record.get("phase", "-"))[:10]
    actor = str(record.get("actor", "-"))[:10]
    print(f"  [{phase:<10}] {actor:<10} {record.get('action', '')} -> {record.get('status', '')}")


# --------------------------------------------------------------------------- 状态与锁

def state_path(task_id: str) -> Path:
    return RUNTIME / "state" / f"{task_id}.json"


def save_state(state: dict) -> None:
    write_json(state_path(state["task_id"]), state)


def load_state(task_id: str) -> dict:
    p = state_path(task_id)
    if not p.exists():
        raise SystemExit(f"找不到任务状态：{p}（先 run 一次）")
    return read_json(p)


class TaskLock:
    """跨进程单写者锁：拿不到就拒绝启动，绝不排队猜。"""

    def __init__(self, task_id: str) -> None:
        self.path = RUNTIME / "locks" / f"{task_id}.lock"

    def __enter__(self) -> "TaskLock":
        for _ in range(2):
            try:
                fd = os.open(self.path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
                os.write(fd, json.dumps({"pid": os.getpid(), "ts": now_iso()}).encode("utf-8"))
                os.close(fd)
                return self
            except FileExistsError:
                age = time.time() - self.path.stat().st_mtime
                if age > 7200:  # 2 小时视为陈旧锁
                    self.path.unlink(missing_ok=True)
                    continue
                raise SystemExit(
                    f"任务被占用：{self.path}（{int(age)}s）\n"
                    "确认没有其他 producer 在跑，或手动删除该 lock 文件。"
                )
        raise SystemExit("无法获取任务锁")

    def __exit__(self, *exc) -> None:
        self.path.unlink(missing_ok=True)


# --------------------------------------------------------------------------- 仓库与 worktree

def ensure_repo() -> None:
    if not (PROJECT / ".git").exists():
        raise SystemExit(
            f"{PROJECT} 不是 git 仓库。\n先运行：python orchestrator.py bootstrap"
        )


def cmd_bootstrap(_args) -> int:
    PROJECT.mkdir(parents=True, exist_ok=True)
    if not (PROJECT / ".git").exists():
        git(["init", "-b", "main"], cwd=PROJECT)
        print(f"[INIT] git 仓库已创建：{PROJECT}")
    git(["config", "user.name", "MultiAgent Pipeline"], cwd=PROJECT)
    git(["config", "user.email", "pipeline@local"], cwd=PROJECT)
    git(["add", "-A"], cwd=PROJECT)
    if git(["status", "--porcelain"], cwd=PROJECT).stdout.strip():
        git(["commit", "-m", "baseline: 定价卡片 + 冻结的验收测试（red）"], cwd=PROJECT)
        print("[OK] 基线已提交（此时期望测试为红）")
    else:
        print("[OK] 工作区干净，无需提交")
    print(f"     HEAD = {git_out(['rev-parse', '--short', 'HEAD'])}")
    return 0


def worktree_dir(task_id: str, round_no: int) -> Path:
    return (ROOT / BASE_CFG["worktree_root"] / f"{task_id}-r{round_no}").resolve()


def create_worktree(task_id: str, branch: str, base: str) -> Path:
    wt = worktree_dir(task_id, 1)
    if wt.exists():
        shutil.rmtree(wt, ignore_errors=True)
    git(["worktree", "prune"], check=False)
    if git_out(["branch", "--list", branch]):
        git(["branch", "-D", branch])
    git(["worktree", "add", "-b", branch, str(wt), base])
    return wt


def remove_worktree(wt: Path) -> None:
    git(["worktree", "remove", "--force", str(wt)], check=False)
    git(["worktree", "prune"], check=False)


# --------------------------------------------------------------------------- 一轮产出

def apply_seed(seed_dir: Path, wt: Path) -> list[str]:
    """把 planner 预先写好的文件（通常是冻结的验收测试）铺进 worktree。"""
    files: list[str] = []
    for f in sorted(seed_dir.rglob("*")):
        if not f.is_file():
            continue
        rel = f.relative_to(seed_dir)
        dst = wt / rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(f, dst)
        files.append(rel.as_posix())
    return files


def commit_round(wt: Path, spec: dict, round_no: int, worker: str) -> str:
    if not git(["status", "--porcelain"], cwd=wt).stdout.strip():
        raise RuntimeError(f"第 {round_no} 轮：producer 没有产生任何可提交的改动")
    git(["add", "-A"], cwd=wt)
    msg = f"feat({spec['id']}): 第 {round_no} 轮产出\n\nProduced-by: {worker}\nRound: {round_no}"
    git(["commit", "-m", msg], cwd=wt)
    return git_out(["rev-parse", "HEAD"], cwd=wt)


def repair_loop(cfg: dict, state: dict, spec: dict, wt: Path,
                start_round: int, feedback: dict | None) -> tuple[bool, dict | None]:
    max_rounds = int(spec.get("max_repair_rounds", 2))
    diff_base = state.get("diff_base") or state["base_commit"]
    for round_no in range(start_round, max_rounds + 1):
        state["round"] = round_no
        state["phase"] = "produce"
        save_state(state)
        print(f"\n=== 第 {round_no}/{max_rounds} 轮：producer 产出 ===")

        result = workers.produce(cfg, spec, wt, round_no, feedback, RUNTIME, ROOT)
        ledger(phase="produce", actor=result["worker"], action=f"round {round_no}",
               status="ok", files=result.get("files"), note=result.get("note"))

        head = commit_round(wt, spec, round_no, result["worker"])
        ledger(phase="commit", actor="orchestrator", action=f"round {round_no}",
               status="ok", commit=head[:10])

        diff_text = git(["diff", f"{diff_base}..HEAD"], cwd=wt).stdout
        diff_path = RUNTIME / "artifacts" / f"{spec['id']}-r{round_no}.diff"
        diff_path.write_text(diff_text, encoding="utf-8")

        state["phase"] = "verify"
        save_state(state)
        results = checks_mod.run_all(cfg, wt, spec, diff_base)
        for c in results:
            ledger(phase="verify", actor="dsh", action=c["id"], status=c["status"],
                   detail=c["detail"][:180])

        failed = [c for c in results if c["status"] == "fail"]
        state.setdefault("attempts", []).append({
            "round": round_no,
            "worker": result["worker"],
            "commit": head,
            "checks": results,
            "diff_path": str(diff_path),
        })
        save_state(state)

        if not failed:
            print(f"\n[OK] 第 {round_no} 轮自动检查全部通过")
            return True, None

        feedback = {
            "round": round_no,
            "failed_checks": [
                {"id": c["id"], "detail": c["detail"]} for c in failed
            ],
            "instruction": "只修复上述失败项；不要改 test/ 或 package.json，不要扩大改动范围。",
        }
        write_json(RUNTIME / "handoffs" / f"{spec['id']}-r{round_no}-feedback.json", feedback)
        print(f"\n[FAIL] 第 {round_no} 轮未通过：{[c['id'] for c in failed]}")
        if round_no == max_rounds:
            state["status"] = "failed"
            state["phase"] = "failed"
            save_state(state)
            report = write_report(state, spec, None)
            print(f"[STOP] 修复轮次用尽，任务失败。报告：{report}")
            return False, feedback

    return False, feedback


# --------------------------------------------------------------------------- 评审交接

VERDICT_SCHEMA = {
    "task_id": "str",
    "round": "int",
    "verdict": "pass | fail",
    "reviewer": "str",
    "risk_level": "low | medium | high",
    "blocking": [{"issue": "str", "evidence": "str", "suggestion": "str"}],
    "advisory": [{"issue": "str", "suggestion": "str"}],
}


def write_review_request(state: dict, spec: dict, wt: Path) -> Path:
    base = state.get("diff_base") or state["base_commit"]
    changed = [ln.strip() for ln in
               git(["diff", "--name-only", f"{base}..HEAD"], cwd=wt).stdout.splitlines()
               if ln.strip()]
    last = state["attempts"][-1]
    verdict_path = RUNTIME / "handoffs" / f"{spec['id']}-review-verdict.json"
    request = {
        "task_id": spec["id"],
        "title": spec["title"],
        "round": state["round"],
        "branch": state["branch"],
        "base_commit": base,
        "worktree": str(wt),
        "producer": last["worker"],
        "changed_files": changed,
        "acceptance": spec.get("acceptance", []),
        "auto_checks": [{"id": c["id"], "status": c["status"], "detail": c["detail"]}
                        for c in last["checks"]],
        "diff_path": str(last["diff_path"]),
        "verdict_path": str(verdict_path),
        "instructions": (
            "你是 DSH reviewer。请阅读 diff_path 指向的 diff、auto_checks 与 acceptance，"
            "判断这次改动是否可以合并：关注正确性边界、错误处理、可维护性、与既有风格一致性、"
            "以及自动检查覆盖不到的风险。把裁决写入 verdict_path（严格按 verdict_schema 的 JSON）。"
            "只有会导致线上问题或明显缺陷的才放进 blocking；风格建议放 advisory。"
        ),
        "verdict_schema": VERDICT_SCHEMA,
    }
    path = RUNTIME / "handoffs" / f"{spec['id']}-review-request.json"
    write_json(path, request)
    return path


def read_verdict(path: Path, task_id: str) -> dict:
    if not path.exists():
        raise SystemExit(f"找不到裁决文件：{path}\n请先让 DSH reviewer 写入后再 resume。")
    data = read_json(path)
    for key in ("task_id", "round", "verdict", "reviewer"):
        if key not in data:
            raise SystemExit(f"裁决缺少字段 `{key}`：{path}")
    if data["verdict"] not in ("pass", "fail"):
        raise SystemExit(f"verdict 必须是 pass/fail，实际：{data['verdict']}")
    if data["task_id"] != task_id:
        raise SystemExit(f"裁决的 task_id 不匹配：{data['task_id']} != {task_id}")
    data.setdefault("blocking", [])
    data.setdefault("advisory", [])
    return data


# --------------------------------------------------------------------------- 合并

def integrate(state: dict, spec: dict, verdict: dict | None) -> None:
    branch = state["branch"]
    current = git_out(["rev-parse", "--abbrev-ref", "HEAD"])
    if current != BASE_CFG["integration_branch"]:
        git(["checkout", BASE_CFG["integration_branch"]])

    drifted = git_out(["rev-parse", "HEAD"]) != state["base_commit"]
    if drifted:
        ledger(phase="integrate", actor="dsh", action="base 漂移",
               status="warn", detail="集成分支在任务期间前进过，合并可能冲突")

    body = [f"merge: {spec['title']} ({spec['id']})", ""]
    body.append(f"Produced-by: {state['attempts'][-1]['worker']}")
    if verdict:
        body.append(f"Reviewed-by: {verdict.get('reviewer', 'dsh-reviewer')} "
                    f"(risk={verdict.get('risk_level', '-')})")
    body.append(BASE_CFG["integrator"]["coauthor_trailer"])

    p = git(["merge", "--no-ff", branch, "-m", "\n".join(body)], check=False)
    if p.returncode != 0:
        git(["merge", "--abort"], check=False)
        state["status"] = "merge_conflict"
        state["phase"] = "failed"
        save_state(state)
        raise RuntimeError(f"合并冲突，已 abort：\n{(p.stdout or '')[-800:]}\n{(p.stderr or '')[-800:]}")

    merge_head = git_out(["rev-parse", "HEAD"])
    ledger(phase="integrate", actor="dsh", action="merge --no-ff", status="ok",
           commit=merge_head[:10])
    state["status"] = "done"
    state["phase"] = "done"
    state["merge_commit"] = merge_head
    save_state(state)
    report = write_report(state, spec, verdict)
    print(f"\n[OK] 已合并到 {BASE_CFG['integration_branch']}：{merge_head[:10]}")
    print(f"     报告：{report}")
    remove_worktree(Path(state["worktree"]))


# --------------------------------------------------------------------------- 报告

def write_report(state: dict, spec: dict, verdict: dict | None) -> Path:
    lines = [
        f"# 多 Agent 运行报告：{spec['title']}",
        "",
        f"- 任务：`{spec['id']}`",
        f"- 分支：`{state.get('branch', '-')}`",
        f"- 基线：`{state.get('base_commit', '-')[:10]}`",
        f"- 状态：**{state.get('status')}**",
        f"- 生成时间：{now_iso()}",
        "",
        "## 轮次",
        "",
        "| 轮 | 产出方 | commit | 自动检查 |",
        "|---|---|---|---|",
    ]
    for a in state.get("attempts", []):
        failed = [c["id"] for c in a["checks"] if c["status"] == "fail"]
        lines.append(
            f"| {a['round']} | {a['worker']} | `{a['commit'][:10]}` | "
            f"{'全部通过' if not failed else '未通过：' + ', '.join(failed)} |"
        )

    if verdict:
        lines += ["", "## 评审", "",
                  f"- 评审人：{verdict.get('reviewer')}",
                  f"- 结论：**{verdict.get('verdict')}**（风险 {verdict.get('risk_level', '-')}）"]
        for b in verdict.get("blocking", []):
            lines.append(f"- 阻塞：{b.get('issue')} — {b.get('suggestion', '')}")
        for b in verdict.get("advisory", []):
            lines.append(f"- 建议：{b.get('issue')} — {b.get('suggestion', '')}")

    lines += ["", "## 自动检查明细", ""]
    for a in state.get("attempts", []):
        lines.append(f"### 第 {a['round']} 轮（{a['worker']}）")
        for c in a["checks"]:
            lines.append(f"- `{c['id']}` **{c['status']}** — {c['detail']}")
        lines.append("")

    path = RUNTIME / "reports" / f"{spec['id']}-report.md"
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


# --------------------------------------------------------------------------- 子命令

def load_spec(raw: str) -> tuple[dict, Path]:
    path = Path(raw)
    if not path.is_absolute():
        path = (ROOT / raw).resolve()
    if not path.exists():
        raise SystemExit(f"找不到任务契约：{path}")
    spec = read_json(path)
    for key in ("id", "title", "owner_globs", "acceptance"):
        if key not in spec:
            raise SystemExit(f"任务契约缺少字段 `{key}`：{path}")
    return spec, path


def cfg_with_mode(mode: str | None) -> dict:
    cfg = copy.deepcopy(BASE_CFG)
    if mode:
        cfg["producer"]["mode"] = mode
    return cfg


def cmd_run(args) -> int:
    ensure_repo()
    cfg = cfg_with_mode(args.mode)
    spec, spec_path = load_spec(args.task)

    print(f"\n任务：{spec['title']}")
    print(f"产出方：{cfg['producer']['mode']} / 验收：{cfg['checks']['test_cmd'][0]} / 集成分支：{cfg['integration_branch']}")

    with TaskLock(spec["id"]):
        base = git_out(["rev-parse", cfg["integration_branch"]])
        state = {
            "task_id": spec["id"],
            "title": spec["title"],
            "spec_path": str(spec_path.relative_to(ROOT)),
            "phase": "plan",
            "round": 0,
            "status": "running",
            "branch": f"agent/{spec['id']}",
            "base_commit": base,
            "attempts": [],
            "producer_mode": cfg["producer"]["mode"],
            "created_at": now_iso(),
        }
        save_state(state)

        ledger(phase="plan", actor="dsh", action="加载任务契约 + 冻结验收测试",
               status="ok", task=spec["id"], base=base[:10])

        wt = create_worktree(spec["id"], state["branch"], base)
        state["worktree"] = str(wt)
        save_state(state)
        ledger(phase="worktree", actor="orchestrator", action="隔离工作区",
               status="ok", path=str(wt))

        seed = spec.get("planner_seed")
        if seed:
            seed_dir = (ROOT / seed).resolve()
            if not seed_dir.is_dir():
                raise SystemExit(f"planner_seed 目录不存在：{seed_dir}")
            files = apply_seed(seed_dir, wt)
            git(["add", "-A"], cwd=wt)
            git(["commit", "-m",
                 f"spec({spec['id']}): 冻结验收测试（red）\n\nPlanned-by: dsh"], cwd=wt)
            state["diff_base"] = git_out(["rev-parse", "HEAD"], cwd=wt)
            save_state(state)
            ledger(phase="plan", actor="dsh", action="冻结验收测试", status="ok",
                   files=files, commit=state["diff_base"][:10])

        ok, _feedback = repair_loop(cfg, state, spec, wt, 1, None)
        if not ok:
            return 1

        if spec.get("requires_review", True):
            request = write_review_request(state, spec, wt)
            state["status"] = "awaiting_review"
            state["phase"] = "review"
            save_state(state)
            print(f"\n[PAUSE] 自动检查通过，等待 DSH reviewer 裁决")
            print(f"        请求：{request}")
            print(f"        裁决写入后运行：python orchestrator.py resume --task-id {spec['id']}")
            return 3

        integrate(state, spec, None)
        return 0


def cmd_resume(args) -> int:
    ensure_repo()
    state = load_state(args.task_id)
    cfg = cfg_with_mode(args.mode or state.get("producer_mode"))
    spec, _ = load_spec(state["spec_path"])
    with TaskLock(spec["id"]):
        return _resume_locked(cfg, state, spec)


def _resume_locked(cfg: dict, state: dict, spec: dict) -> int:
    if state.get("status") != "awaiting_review":
        raise SystemExit(f"任务当前状态为 {state.get('status')}，不是 awaiting_review，无需 resume")

    wt = Path(state["worktree"])
    verdict_path = RUNTIME / "handoffs" / f"{spec['id']}-review-verdict.json"
    verdict = read_verdict(verdict_path, spec["id"])
    ledger(phase="review", actor=str(verdict.get("reviewer", "dsh")),
           action=f"verdict={verdict['verdict']}", status="ok",
           risk=verdict.get("risk_level", "-"),
           blocking=len(verdict["blocking"]), advisory=len(verdict["advisory"]))

    if verdict["verdict"] == "pass" and not verdict["blocking"]:
        integrate(state, spec, verdict)
        return 0

    print(f"\n[FAIL] 评审未通过（blocking={len(verdict['blocking'])}），进入修复轮")
    feedback = {
        "source": "reviewer",
        "reviewer": verdict.get("reviewer"),
        "blocking": verdict["blocking"],
        "advisory": verdict.get("advisory", []),
        "instruction": "只修复 blocking 项；advisory 可选择性处理并在说明里写清楚。",
    }
    write_json(RUNTIME / "handoffs" / f"{spec['id']}-r{state['round']}-review-feedback.json", feedback)

    next_round = int(state["round"]) + 1
    max_rounds = int(spec.get("max_repair_rounds", 2))
    if next_round > max_rounds:
        state["status"] = "failed"
        state["phase"] = "failed"
        save_state(state)
        write_report(state, spec, verdict)
        print("[STOP] 没有剩余修复轮次")
        return 1

    state["status"] = "running"
    save_state(state)
    try:
        ok, _fb = repair_loop(cfg, state, spec, wt, next_round, feedback)
    except Exception:
        # producer 失败（网络/额度/CLI 异常）不该把任务卡死在 running：
        # 放回评审门，修好环境后可直接重试 resume。
        state["status"] = "awaiting_review"
        state["phase"] = "review"
        save_state(state)
        raise
    if not ok:
        return 1

    request = write_review_request(state, spec, wt)
    state["status"] = "awaiting_review"
    state["phase"] = "review"
    save_state(state)
    print(f"\n[PAUSE] 再次等待评审：{request}")
    return 3


def cmd_doctor(_args) -> int:
    print("\n环境自检")
    print("-" * 64)
    ok = True

    def line(name: str, status: str, detail: str = "") -> None:
        print(f"  {name:<14} {status:<8} {detail}")

    try:
        line("git", "OK", git_out(["--version"]))
    except Exception as exc:
        ok = False
        line("git", "MISSING", str(exc)[:80])

    try:
        line("node", "OK", sh(["node", "--version"]).stdout.strip())
    except Exception as exc:
        ok = False
        line("node", "MISSING", str(exc)[:80])

    line("python", "OK", sys.version.split()[0])

    if (PROJECT / ".git").exists():
        line("项目仓库", "OK", str(PROJECT))
    else:
        ok = False
        line("项目仓库", "MISSING", "先运行 bootstrap")

    cb = BASE_CFG["producer"]["codebuddy"]
    try:
        version = workers._probe(cb["version_cmd"]) or "unknown"
        line("CodeBuddy CLI", "OK", version)
    except Exception:
        ok = False
        line("CodeBuddy CLI", "MISSING", "npm i -g @tencent-ai/codebuddy-code")
        line("", "HINT", "装完先在终端跑一次 codebuddy 完成登录")

    line("producer 模式", BASE_CFG["producer"]["mode"], "（--mode 可临时覆盖）")
    print("-" * 64)
    if ok:
        print("  全部就绪：run.cmd run --task <spec>.json --mode codebuddy")
    else:
        print("  还有缺失项，按上面 HINT 处理后重跑 doctor")
    return 0 if ok else 1


def cmd_gate(args) -> int:
    """CI 门禁：在任何 checkout 上跑确定性检查，不启动 producer。"""
    repo = Path(args.repo).resolve() if args.repo else PROJECT
    if not (repo / ".git").exists():
        raise SystemExit(f"{repo} 不是 git 仓库（子模块/稀疏检出都会导致这个问题）")

    cfg = copy.deepcopy(BASE_CFG)
    spec, _ = load_spec(args.task)
    base = args.base or git_out(["merge-base", cfg["integration_branch"], "HEAD"], cwd=repo)
    seed_dir = (ROOT / spec["planner_seed"]).resolve() if spec.get("planner_seed") else None

    print(f"\nCI 门禁：{spec['title']}")
    print(f"  仓库 {repo}")
    print(f"  范围 {base[:10]}..HEAD")

    results = checks_mod.run_gate(cfg, repo, spec, base, seed_dir)
    for c in results:
        mark = {"pass": "PASS", "fail": "FAIL"}.get(c["status"], "SKIP")
        print(f"  [{mark}] {c['id']:<8} {c['detail'][:120]}")

    failed = [c for c in results if c["status"] == "fail"]
    head = git_out(["rev-parse", "--short", "HEAD"], cwd=repo)
    record = {"ts": now_iso(), "task": spec["id"], "repo": str(repo), "base": base,
              "head": head, "passed": not failed, "checks": results}
    out = RUNTIME / "gates" / f"{spec['id']}-{head}-{int(time.time())}.json"
    write_json(out, record)
    print(f"\n  报告 {out}")

    if failed:
        print(f"\n[FAIL] {len(failed)} 项未通过：{', '.join(c['id'] for c in failed)}")
        return 1
    print("\n[OK] 门禁通过")
    return 0


def cmd_status(args) -> int:
    state = load_state(args.task_id)
    print(json.dumps(state, ensure_ascii=False, indent=2))
    ledger_path = RUNTIME / "ledger.jsonl"
    if ledger_path.exists():
        tail = ledger_path.read_text(encoding="utf-8").splitlines()[-8:]
        print("\n最近事件：")
        for line in tail:
            print("  " + line)
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="CodeBuddy x DSH 多 Agent 流水线")
    sub = parser.add_subparsers(dest="cmd", required=True)

    sub.add_parser("bootstrap", help="初始化 demo 仓库并提交基线")
    sub.add_parser("doctor", help="自检 git / node / 仓库 / CodeBuddy CLI")

    p_run = sub.add_parser("run", help="规划 -> 产出 -> 验证（如通过则暂停等待评审）")
    p_run.add_argument("--task", required=True, help="任务契约 JSON 路径")
    p_run.add_argument("--mode", choices=["mock", "codebuddy"], default=None,
                       help="覆盖 config.json 里的 producer 模式")

    p_resume = sub.add_parser("resume", help="读取评审裁决并合并/继续修复")
    p_resume.add_argument("--task-id", required=True)
    p_resume.add_argument("--mode", choices=["mock", "codebuddy"], default=None)

    p_status = sub.add_parser("status", help="打印任务状态")
    p_status.add_argument("--task-id", required=True)

    p_gate = sub.add_parser("gate", help="CI 门禁：只跑确定性检查，不调模型/不联网")
    p_gate.add_argument("--task", required=True, help="任务契约 JSON 路径")
    p_gate.add_argument("--base", default=None, help="对比基线（默认与集成分支的 merge-base）")
    p_gate.add_argument("--repo", default=None, help="要检查的 checkout（默认 config.project_dir）")

    args = parser.parse_args()
    handlers = {"bootstrap": cmd_bootstrap, "doctor": cmd_doctor, "run": cmd_run,
                "resume": cmd_resume, "status": cmd_status, "gate": cmd_gate}
    try:
        return handlers[args.cmd](args)
    except RuntimeError as exc:
        print(f"\n[ERROR] {exc}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
