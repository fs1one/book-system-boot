# CodeBuddy × DSH 多 Agent 流水线

把两个 agent 的长处拆开用，而不是让它们对同一个文件并行乱写：

| 角色 | 谁 | 只做它擅长的事 | 明确不做 |
|---|---|---|---|
| **planner** | DSH | 读仓库、写任务契约、**先写验收测试并冻结** | 不写业务实现 |
| **producer** | CodeBuddy | UI / 前端 / 设计稿落地 / IDE 内迭代，在隔离 worktree 里改文件 | 不写验收测试、不提交、不合并 |
| **verifier** | DSH | 确定性检查（测试/范围/凭据/UI 契约/体积）+ 判断性评审 | 不改产出方的代码 |
| **integrator** | DSH | 仅 PASS 后合并，写 co-author trailer 与审计账本 | 不替评审做决定 |

> 这套流程能成立的根本原因只有一条：**写测试的人和写实现的人不是同一个 agent**。
> 测试先于实现冻结，产出方就无法“把测试改成能过”。

---

## 架构

```
task spec (JSON)                     ← DSH 写，含 owner_globs / forbidden_globs / acceptance
      │
      ▼
[plan]  检查仓库状态，锁定 base commit
      │
      ▼
[worktree]  git worktree add -b agent/<task> <base>     ← 物理隔离，主分支不受影响
      │
      ▼
┌──────────────── 修复循环（max_repair_rounds） ────────────────┐
│  [produce]  CodeBuddy headless（或 mock）在 worktree 内改文件   │
│      │      owner_globs 之外不许碰，test/ 冻结                │
│      ▼                                                       │
│  [commit]   编排器提交，带 Produced-by trailer                │
│      ▼                                                       │
│  [verify]   6 项确定性检查 + 生成 diff 工件                    │
│      │                                                       │
│      ├─ 有 fail → 写 feedback.json，进入下一轮 ────────────────┘
│      ▼
│   全部 pass
└──────────────────────────────────────────────────────────────┘
      │
      ▼
[review]  DSH reviewer 读 diff + auto_checks → verdict.json
      │        pass 且无 blocking ──► [integrate] merge --no-ff + 报告
      │        fail / 有 blocking ──► 回到修复循环（消耗剩余轮次）
      ▼
   ledger.jsonl（每一步可审计）+ reports/<task>-report.md
```

**交接物只有三种文件**：`task spec`（人→流程）、`feedback.json`（验证→产出）、`verdict.json`（评审→集成）。
两个 agent 从不实时对话，上下文互不污染。

---

## 快速开始

```bat
cd multiagent

:: 0. 自检：git / node / 仓库 / CodeBuddy CLI 是否就绪
run.cmd doctor

:: 1. 初始化 demo 仓库，提交基线（此时验收测试是红的，属预期）
run.cmd bootstrap

:: 2. 跑流水线：第 1 轮故意失败 → 第 2 轮修复 → 停在评审门（退出码 3）
run.cmd run --task demo/specs/pricing-discount-tier.json

:: 3. 让 DSH reviewer 写 verdict.json，然后合并
run.cmd resume --task-id pricing-discount-tier

:: 随时看状态
run.cmd status --task-id pricing-discount-tier
```

`run.cmd` 会自动找 python（PATH → py → DSH 运行时内置）。也可以直接
`python orchestrator.py ...`。

退出码：`0` 完成 / `3` 等待评审 / `1` 失败。

---

## demo 里发生了什么

- 基线 `demo/project`：`computeTotal` 只做线性求和，`test/pricing.test.js` 已写好 8 条验收测试（**红**）。
- 第 1 轮（`demo/mock/pricing-discount-tier/round1`）：实现折扣 + 改 UI，但有两个真实缺陷 ——
  门槛用 `>`（100 元不命中）、取第一个匹配档而不是力度最大档。
  → `tests` 检查失败，`feedback.json` 写回，**不合并**。
- 第 2 轮（`demo/mock/pricing-discount-tier/round2`）：只修 `src/pricing.js`，8/8 通过。
  → 停在评审门，等 DSH reviewer。
- 评审 pass 后 `merge --no-ff` 到 `main`，报告落盘。

`mock` 只是 **producer 适配器的替身**，用于在没有 CodeBuddy 的机器上验证整条流水线（CI、离线环境、契约测试）。
它不代表 CodeBuddy 的行为，也不参与任何质量判断。产物按任务隔离（`demo/mock/<task-id>/roundN`），
不同任务不会串用同一份补丁。

### 第二个任务：`pricing-hardening`（留给真实 CodeBuddy）

第一轮评审提出 6 条 advisory，其中 4 条已经变成新任务的冻结验收测试：

| 任务 | 谁写测试 | 产出方 | 内容 |
|---|---|---|---|
| `pricing-discount-tier` | DSH（已跑完，mock） | mock | 阶梯折扣 + UI 展示 |
| `pricing-hardening` | DSH（`demo/seed/`，运行时铺进 worktree） | **真实 CodeBuddy** | `tiers=null` 容错、字符串 `min`、按分舍入、输入校验、负号格式 |

```bat
run.cmd run --task demo/specs/pricing-hardening.json --mode codebuddy
```

`planner_seed` 机制：测试不预先提交到 `main`（保持主干常绿），而是在创建任务分支后由 DSH 铺入并单独提交
`spec(...): 冻结验收测试（red）`，之后所有 diff 都以这个 commit 为基线——产出方的改动里看不到测试文件。

---

## 接入真实 CodeBuddy

> **CodeBuddy IDE ≠ CodeBuddy Code CLI。** IDE（`CodeBuddy CN.exe`）没有无头模式；
> 流水线要的是 npm 上的 CLI：[`@tencent-ai/codebuddy-code`](https://www.npmjs.com/package/@tencent-ai/codebuddy-code)
> （命令 `codebuddy`，别名 `cbc`）。

```bat
:: 1. 安装（需要联网）
npm install -g @tencent-ai/codebuddy-code

:: 2. 登录（首次会拉起浏览器授权；CLI 凭证与 IDE 不共享）
codebuddy

:: 3. 自检
run.cmd doctor
```

`config.json` 默认已经是校准过的版本：

```json
"producer": {
  "mode": "codebuddy",
  "allow_fallback": true,
  "codebuddy": {
    "cmd": ["codebuddy", "-p", "{prompt}", "--output-format", "json",
            "--permission-mode", "acceptEdits"],
    "version_cmd": ["codebuddy", "--version"],
    "timeout_sec": 900
  }
}
```

参数含义（按 v2.177 的 CLI 参考校准）：

| 参数 | 作用 | 注意 |
|---|---|---|
| `-p` / `--print` | 非交互执行一次后退出 | 不加就是交互式会话，在流水线里会挂住 |
| `--output-format json` | 机器可读输出 | 也支持 `stream-json` |
| `--permission-mode acceptEdits` | 自动接受文件编辑 | 若日志显示工具被权限拦截，再加 `--allowedTools`，或临时改 `--dangerously-skip-permissions`（**仅限隔离沙箱**） |
| `{prompt}` / `{prompt_file}` | 提示词正文 / 提示词文件路径 | 正文过长时改用文件 |

三个必须配到位的点：

1. **权限**：`-p` 模式下任何需要授权的工具默认会被拦。`acceptEdits` 覆盖文件编辑；若它还要跑 `Bash` 自测，需要显式放开。**不要**给 push / 跨目录写权限。
2. **登录态**：CLI 有自己的凭证。过期时退出码非 0，日志在 `.multiagent/artifacts/<task>-r<N>-producer.log`。
3. **配额**：走积分账户，额度耗尽同样表现为非 0；适配器会先 `git status` 校验“确实改了文件”，不会把空产出当成功。

适配器行为：探测版本 → 渲染提示词 → 在 worktree 内执行 → 校验改动 → 返回统一结构。
失败可降级到 mock（`allow_fallback`），降级会明确记进 ledger；若 mock 也没有对应任务产物，会直接报错而不是假装成功。

---

## 契约

### task spec（`demo/specs/*.json`）

| 字段 | 作用 |
|---|---|
| `id` / `title` | 任务标识与标题 |
| `owner_globs` | **白名单**：允许改的文件，越界即 fail |
| `forbidden_globs` | **黑名单**：`test/**` 必须在这里 |
| `planner_seed` | 可选：DSH 预先写好的文件目录（通常是冻结测试），创建分支后铺入并单独提交 |
| `acceptance` | 验收标准（提示词会带上，评审也对照它） |
| `max_repair_rounds` | 修复轮上限，默认 2 |
| `requires_review` | 是否必须过评审门 |

### verdict（`.multiagent/handoffs/<task>-review-verdict.json`）

```json
{
  "task_id": "pricing-discount-tier",
  "round": 2,
  "verdict": "pass",
  "reviewer": "dsh-reviewer (subagent)",
  "risk_level": "low",
  "blocking": [],
  "advisory": [{ "issue": "...", "suggestion": "..." }]
}
```

`verdict=pass` 且 `blocking` 为空才合并；`blocking` 会变成下一轮的 feedback。

### ledger（`.multiagent/ledger.jsonl`）

每行一个事件：`ts / phase / actor / action / status`，另带 `commit`、`detail`、`files` 等。
谁在哪一轮改了什么、哪项检查挂了、合并到哪个 commit，都能回溯。

---

## 六项确定性检查

| id | 判什么 | 为什么由 DSH 做 |
|---|---|---|
| `changed` | 是否真有改动 | 防“空产出假装完成” |
| `scope` | 改动是否越界 / 碰了 `test/` | 规则判定，不该靠模型自觉 |
| `tests` | 冻结的验收测试是否全绿 | 可重复、可进 CI |
| `secrets` | 新增行是否含凭据特征 | 正则比模型可靠 |
| `ui` | 页面是否满足契约标记（`id=savings` 等） | UI 也可以有结构性断言 |
| `size` | diff 行数是否超限 | 逼任务拆分，防“大爆炸式提交” |

判断性评审（可维护性、可访问性、边界风险）不塞进脚本，交给 reviewer 的 `advisory`，避免用假确定性掩盖真判断。

---

## 实战记录（2026-10-29，真实 CodeBuddy v2.177.1 → 2.178.1）

第一次用真 CLI 跑 `pricing-hardening`，两轮闭环：

| 轮 | 自动检查 | 关键事件 |
|---|---|---|
| 1 | 6/6 通过 | 7 条冻结测试一次通过；实现用「分」运算、类型校验、错误带字段名 |
| review | **fail，blocking 1** | `Number(null) === 0`：`min: null` 被当成门槛 0，`computeTotal([{price:100}], [{min:null,rate:0.5}]) === 50`——等于给所有订单打五折 |
| 2 | 6/6 通过 | 加 `normalizeTierMin` 严格正则、非法档位跳过并告警、符号感知舍入、`items` 容器校验 |
| review | **pass，risk medium** | blocking 清零，剩 6 条 advisory（`rate` 未校验会免单、`-¥0.00`、`"1e2"` 被拒、NodeList 静默失效…） |
| merge | — | `f740b71`，15/15 测试通过 |

从 JSON 输出里能直接读到的事实：

- **模型路由**：不指定 `--model` 时默认走 `hy4-preview`（混元 4）；加上 `--model deepseek-v4.1-flash` 后实测确实切到 DeepSeek。每步 `prompt_tokens` / `completion_tokens` 都在，可做成本归因。
- **工具白名单确实生效**：它试图调用 `Bash`，被 `--tools` 挡掉（`Tool "Bash" does not exist in the current tool set`），随后改用 Read/Edit 完成。想让它自己跑测试得显式放开。
- **中文读取有编码缺陷**：Read UTF-8 中文文件时按 GBK 解码，日志里是 `���ۺ����߼�`。这次代码是 ASCII 所以没翻车，中文密集的仓库要留意。
- **沙箱挡网络**：普通权限下 `curl` 全 `000`，full-access 下 `200`。真实 producer 必须能联网，且要写 `~/.codebuddy`。
- **模式要持久化**：`resume` 原本会退回默认 `mock`，现在 producer 模式写进 state，resume 自动沿用。

### 换成 DeepSeek 模型后的一轮（`pricing-hardening-2`）

`--model deepseek-v4.1-flash` 下**一次通过**：10 条新冻结测试（rate 校验、溢出、负零、min 科学计数法、BigInt/循环引用、Set/类数组）全绿，
5 步、prompt 73,255 tok / completion 5,785 tok，工具只用 `Read/Glob/Write`，没有无效的 Bash 尝试。评审 pass。

但评审仍挖出两条值得记的真实问题：

- **正则回溯**：`"9" × 40000 + "x"` 匹配耗时 2.7s（旧正则 0.9s）——指数分支放大了回溯；`raw.length > 64` 直接拒绝即可 O(1)。
- **类数组 length 无上限**：`{length: 1e9}` 会尝试分配十亿个 undefined 档位，浏览器里直接卡死/OOM。

这两条都不是测试能覆盖的，只能靠人（或 reviewer）去想「调用方会怎么用错」。

---

## 生产化还缺什么

- **并行任务**：当前一 task 一锁，多任务可并行但要按 `owner_globs` 做全局互斥（同一文件不能被两个 producer 同时改）。
- **真实 DSH 集成**：reviewer 目前是人工/子代理写文件；要全自动可接 ACP 或 SDK（CodeBuddy 侧有 ACP / Python / TS SDK / HTTP API，但多为 Beta，需锁定版本 + 契约测试）。
- **成本记账**：CodeBuddy 积分不透明，建议在 ledger 里记 `credits_before/after`（若 CLI 输出）或至少记轮次与耗时，按任务归因。
- **多仓库 / monorepo**：`owner_globs` 需要按包路径生成，worktree 数量会涨，需清理策略。
- **评审校准**：reviewer 的 blocking 阈值要用历史 PR 校准，否则会退化成“什么都放行”或“什么都拦”。

---

## 已知边界

- `node --test` 在本机沙箱里会 `spawn EPERM`（禁止管道式子进程），所以默认加了 `--test-isolation=none`（Node ≥ 22）。换环境可去掉。
- Windows 上 npm 全局安装出来的是 `codebuddy.cmd` 批处理 shim，`subprocess` 不能直接执行；worker 会解析 shim 找到真实 JS 入口，用 `node cli.js` 直接跑，避免把多行中文提示词塞进 `cmd.exe` 的引号规则里。
- Windows 路径、中文文件名都按 UTF-8 处理；`git worktree` 放在 `.worktrees/`。
- demo 仓库在 `demo/project` 内独立初始化，不碰工作区其它文件。

清理：

```bat
git -C demo/project worktree remove --force ..\.worktrees\pricing-discount-tier-r1
git -C demo/project branch -D agent/pricing-discount-tier
```

重跑第一个 demo 前要把仓库退回基线（`main` 已含合并结果，否则 producer 改动为空）：

```powershell
git -C demo/project reset --hard $(git -C demo/project rev-list --max-parents=0 HEAD)
```

### 第三轮：日志/资源通道（`pricing-hardening-3`）

这轮第一次出现 **blocking 完全来自「非功能面」**：功能验收 7/7 全过、30/30 测试绿，但评审实测
`describe()` 把脏值原样拼进告警和 `TypeError`——1MB 的 `min` 产生 1,000,051 字节日志，
10000 个档位共享一个 1KB 脏 `min` 时单次调用写盘 10.79MB（输入 81KB，放大 130 倍），
1000 × 40KB 场景外推 1 万个约 382MB/次。round 2 截断 + 聚合后：

| 场景 | 修复前 | 修复后 |
|---|---|---|
| 1MB `min` 告警 | 1,000,051 B | **259 B** |
| 10000 × 1KB 脏 `min` | 10,538,890 B / 145ms | **479 B / 7.9ms** |
| 1000 × 40KB 脏 `min` | 40,052,890 B | **482 B** |
| 1MB `tiers` 错误信息 | 1,000,029 B | **262 B** |

这轮也暴露了流水线自己的盲区：**冻结测试只能锁住「算得对不对」，锁不住「日志会不会打爆磁盘」**。
用 round-1 的源码配同一套 30 条测试仍然 30/30 通过——说明截断/聚合这段逻辑目前没有任何测试保护。

### 第四轮：把日志路径也变成测试（`pricing-hardening-4`）

惰性 `describe` 后，10000 档 × 40KB 脏值从 **122ms → 3.5ms**（`JSON.stringify` 只调用 2 次）；
新增 `getAppliedTierInfo()`（返回归一化的数字 `rate`，`getAppliedTier` 行为保持不变）；
迭代器超限告警带上已消费数量（10001）。

评审用**上一版源码**配同一套 36 条测试跑出 **33 pass / 3 fail**，确认新测试确实咬住了本轮改动——
这个「拿旧代码验证新测试」的方法值得固化成惯例。

---

## CI 集成：门禁与生产分离

CI 里**不要**跑 CodeBuddy。理由很实际：需要登录态、消耗积分、要外网、耗时不确定。
CI 该做的是**确定性门禁**——它不调模型、不联网、秒级完成，而且能拦住最危险的两类改动：

```bat
python orchestrator.py gate --task demo/specs/pricing-hardening-4.json --base origin/main
```

七项检查里有两项是 CI 专属的：

| 检查 | 判什么 | 为什么只在 CI 有意义 |
|---|---|---|
| `frozen` | 冻结测试是否与任务契约**逐字节**一致 | 管线里测试在 diff_base 之前、根本不在 diff 里；CI 拿到的是整个 PR，必须防「顺手改测试」 |
| `scope` | 改动是否越出 `owner_globs` | 放行 `planner_seed` 里的测试文件，其余越界即 fail |

实测两个负例（在独立 worktree 里提交后跑）：

```
篡改 test/pricing.hardening4.test.js  → [FAIL] frozen  被改动=['test/pricing.hardening4.test.js']  exit 1
修改 package.json                     → [FAIL] scope   越界=['package.json']                        exit 1
```

模板：`ci/github-actions-agent-gate.yml`、`ci/gitlab-agent-gate.yml`。

两个坑（都实测踩过）：

1. **`fetch-depth: 0`**：`gate` 要算 `merge-base`，浅克隆会直接失败。
2. **换行归一化**：Windows 上 `core.autocrlf` 会把 LF 转成 CRLF，`frozen` 一开始因此误报。
   比较前统一 `\r\n → \n`，比的是内容不是工作区风格。

---

## 本仓库的绑定状态（book-system-boot）

| 环节 | 需要什么 | 怎么验证 |
|---|---|---|
| 本地生产（producer） | CodeBuddy CLI **已登录**（登录态不跟随仓库，换机器/换人要各自 `/login`） | `run.cmd doctor --deep`（会发一次最小请求） |
| 本地验证 + 评审 | 无（DSH 侧确定性检查 + 评审） | `run.cmd run --task specs/money-utils.json` |
| CI（`.github/workflows/agent-gate.yml`） | 无登录态、无积分、无外网模型调用 | PR 上自动跑 `gate` |

`gate` 与 `run` 的分工：`run` 会调模型产出代码，只能在本机跑；`gate` 只做确定性判定，所以能进 CI。
