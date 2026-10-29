# 日常操作手册（给人看的）

一句话：**你定义「什么算对」，DSH 写测试和门禁，CodeBuddy 写实现。**

---

## 角色

| 谁 | 干什么 | 不干什么 |
|---|---|---|
| **你** | 提需求、确认验收标准、决定推不推 | 不写实现、不写测试 |
| **DSH**（我） | 读代码 → 写任务契约 + **冻结测试** → 验证 → 评审 → 合并 | 不替你拍产品决策 |
| **CodeBuddy** | 在隔离 worktree 里按契约改代码 | 不写测试、不提交、不合并 |

关键：写测试的和写实现的**不是同一个**，所以测试改不动，评审才有东西可审。

---

## 标准流程

### 1. 你提需求（一句话就够）

```
仓库 D:\mywebapps\book-system-boot
要做：图书列表支持分页（page/size，size 上限 100）
范围：BookController、BookService、BookServiceImpl
```

**说行为，不要说实现**。「用 PageHelper 插件」是实现，「返回 total 和 records」是行为。
范围尽量窄——1~3 个文件最好，超过就先拆。

### 2. 我写契约 + 测试，你确认

我会给你两样东西：

- `multiagent/specs/<id>.json` —— 验收标准（人话）
- `multiagent/seeds/<id>/src/test/...` —— 冻结测试（机器话）

**这是唯一需要你认真看的一步。** 测试就是合同：它写了什么，CodeBuddy 就只需要做到什么；
它没写的，后面评审也未必拦得住。重点看边界：空值、非法值、上限、并发、精度。

### 3. 我跑流水线

```bat
cd multiagent
run.cmd run --task specs/<id>.json
run.cmd resume --task-id <id>
```

中间不用你管。产出 → 6 项确定性检查 → 独立评审 → 合并 / 打回重做（最多 2 轮）。

### 4. 你看报告，决定推不推

```bat
type multiagent\.multiagent\reports\<id>-report.md
```

报告里有：每轮改了什么、哪项检查挂了、评审的 blocking 和 advisory、合并到哪个 commit。
**advisory 不用全修**——它们是给下一个任务的输入，不是债务。

### 5. 推 / 开 PR

```bat
git push origin main          # 或者开 PR，让 CI 跑 gate
```

CI 只看 `gate`：冻结测试有没有被改、改动有没有越界、`mvn test` 过不过。它不调模型、不烧积分。

---

## 三种场景怎么套

| 场景 | 怎么做 | 注意 |
|---|---|---|
| **新功能** | 完整流程 | 第一次做小一点，先跑通再放大 |
| **修 bug** | 先写**复现测试**（此时红）→ 让 CodeBuddy 修 → 转绿即修好 | 这是这套流程最爽的场景：修完不会复发 |
| **改文案/样式/配置** | 别走流程，直接改或交互式用 CodeBuddy | 杀鸡不用牛刀 |

---

## 开场模板（复制改一下就行）

```
仓库 <路径>
要做：<一句话行为>
范围：<文件或模块>
约束：<不能改什么、性能要求、兼容性>
```

我会先读代码，再回来找你确认验收标准——**不要跳过确认**，那是唯一能拦住「做对了但做错事」的环节。

---

## 反模式（这几件事别做）

| 别做 | 为什么 |
|---|---|
| 「把这个模块重构一下」 | diff 上千行，评审失去意义。拆成 5 个小任务 |
| 跳过测试直接让它改 | 退化成普通 AI 补全，门禁全是空的 |
| 让它改 `pom.xml` / 测试 / CI 配置 | 这些是契约的一部分，已在 `forbidden_globs` 里 |
| 一轮没过就手动改代码 | 让 feedback 走完第 2 轮，否则你不知道是模型不行还是任务没定义好 |
| 把 advisory 当必须修 | 只有 blocking 挡合并；advisory 是下一轮的素材 |

---

## 命令速查

```bat
cd <repo>\multiagent

run.cmd doctor --deep                 :: 环境 + 登录态（会发一次最小请求）
run.cmd run --task specs\x.json       :: 跑任务，通过则暂停等评审
run.cmd resume --task-id x            :: 读裁决，合并或继续修
run.cmd status --task-id x            :: 看状态 + 最近事件
run.cmd gate --task specs\x.json --base origin/main   :: CI 门禁（不调模型）
```

产物都在 `multiagent/.multiagent/`（已 gitignore）：

```
ledger.jsonl      每一步的审计流水
artifacts/        每轮 diff、producer 日志、提示词
handoffs/         评审请求 / 裁决 / 反馈
reports/          人看的运行报告
```

---

## 成本

- 一个中等任务（1~3 文件、几轮修复）大约几十积分，`deepseek-v4.1-flash` 更便宜
- 想指定模型：改 `config.json` 里 `--model`，可选值见 `codebuddy --help`
- 余额和明细在 codebuddy.ai 的用量页；`doctor --deep` 失败通常就是额度或登录态问题

---

## 记住一件事

**每条冻结测试，都是你以后不用再向 AI 解释一遍的需求。**
测试写得越像合同，这套流程越值钱；测试糊弄，它就是个昂贵的代码补全。
