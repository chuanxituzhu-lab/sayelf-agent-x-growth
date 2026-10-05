<p align="center">
  <img src="assets/sayelf-logo.png" alt="SAYELF 山野精灵" width="220">
</p>

<h1 align="center">SAYELF · X Growth Agent</h1>
<p align="center">X TODAY · Evidence-led content, human-approved</p>
<p align="center"><a href="#简体中文">简体中文</a> · <a href="#english">English</a></p>

---

## 简体中文

**核心观点：好的 X 内容来自真实工作和可核验证据，不靠追热点、编造经历或堆点赞。** 系统把素材整理成最多两种表达，检查证据与公开条件，再交给人决定是否发布。

### 下载最新公开版本

[下载 GitHub `main` 最新源码 ZIP](https://github.com/chuanxituzhu-lab/sayelf-agent-x-growth/archive/refs/heads/main.zip) · [查看 Releases](https://github.com/chuanxituzhu-lab/sayelf-agent-x-growth/releases)

ZIP 始终跟随 `main` 上**最新已公开**的代码。本地尚未发布的更新不会出现在其中。仓库目前没有预构建安装包，下载内容是源码。当前 X Growth 所需的 Agent Ops 共享运行时扩展尚未进入 Agent Ops 公开 `main`，因此该 ZIP 暂不能仅凭公开版 Agent Ops 独立运行。

### 做什么

- 点击生成，或由本机每天 08:00（东京时间）准备当天候选；每个账号每天最多两条。
- 为同一条真实工作素材生成两种 X 原生表达，原始素材语言保持不变。
- 支持中文和英文界面；东京 / Worldwide 热点仅作背景，不会自动写入未经证实的事实。
- 事实证据不足、素材不是公开级别或合规审核未通过时，内容保持 `BLOCKED`；分数不能覆盖硬门槛。
- 人工审核后可进行本地发布演练。真实发布仅规划为官方 X API 路径，需要单独完成授权与启用。

### 核心边界

不自动回复、私信、点赞、关注或发布热点内容；不通过浏览器写入 X。草稿、证据和分析数据保存在本机。复盘关注回复、引用、主页访问、关注转化及负向信号，不以点赞优化。当前内容采用本地结构化写法，尚未连接生成式模型；热点读取和 Agent Ops 工作事件也需本机配置后才可用。

### 运行

需要 Windows、Python 3.11+，以及包含 X Growth 共享运行时扩展的 SAYELF Agent Ops 版本。该兼容扩展目前仍在本地开发分支，尚未随公开 `main` 发布。将两个项目放在同一父目录，在本项目目录用 PowerShell 启动：

```powershell
.\run.ps1
```

打开 [http://127.0.0.1:8765](http://127.0.0.1:8765)。每日自动准备可选用 `install_daily.ps1` 安装本机计划任务；用 `uninstall_daily.ps1` 移除该任务。运行、数据边界和当前验收状态见 [ACCEPTANCE](docs/ACCEPTANCE.md) 与 [BUILD_DECISION](docs/BUILD_DECISION.md)。

---

## English

**Core idea: good X content starts with real work and verifiable evidence—not trend chasing, fabricated experience, or like counts.** The system shapes a source into up to two options, checks evidence and publication rules, then leaves the decision to a human.

### Download the latest public version

[Download the latest source ZIP from GitHub `main`](https://github.com/chuanxituzhu-lab/sayelf-agent-x-growth/archive/refs/heads/main.zip) · [View Releases](https://github.com/chuanxituzhu-lab/sayelf-agent-x-growth/releases)

The ZIP follows the **latest code published** on `main`. Local changes that have not been released publicly are not included. There is no prebuilt installer yet. The Agent Ops shared-runtime extension required by X Growth has not reached the public Agent Ops `main`, so this ZIP cannot yet run with the public Agent Ops version alone.

### What it does

- Generate candidates on demand or prepare them locally at 08:00 Tokyo time; up to two per account per day.
- Turn one real work signal into two X-native angles while preserving the source language.
- Provide a Chinese/English interface. Tokyo / Worldwide trends are context only and do not add unverified claims.
- Keep drafts `BLOCKED` when evidence is missing, the source is not classified Public, or compliance review is incomplete. A score cannot override a hard gate.
- Support human review and local publication rehearsal. Live publishing is planned only through the official X API and requires separate authorization and enablement.

### Boundaries

No automatic replies, DMs, likes, follows, trend publishing, or browser-based X writes. Drafts, evidence, and analytics stay on this computer. Learning focuses on replies, quotes, profile visits, follow conversion, and negative signals—not likes. Copy is currently produced with local structural framing; no generative model is connected. Trend reads and Agent Ops work events also require local configuration.

### Run

Requires Windows, Python 3.11+, and a SAYELF Agent Ops version that includes the X Growth shared-runtime extension. That compatible extension is still on a local development branch and has not been published to public `main`. Place both projects under the same parent directory, then run this in PowerShell from this project:

```powershell
.\run.ps1
```

Open [http://127.0.0.1:8765](http://127.0.0.1:8765). To enable daily preparation, run `install_daily.ps1`; remove that scheduled task with `uninstall_daily.ps1`. See [ACCEPTANCE](docs/ACCEPTANCE.md) and [BUILD_DECISION](docs/BUILD_DECISION.md) for implementation, data boundaries, and current acceptance status.


**Logo / 标识：** The supplied SAYELF artwork is included for this project’s branding. Its reuse rights remain with its respective owner; it is not separately licensed by the source-code MIT license. / 本仓库包含用户提供的 SAYELF 标识用于项目品牌展示；图像权利仍归其权利人所有，不随源码 MIT 许可单独授权。
