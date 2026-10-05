# v0.3 Build Decision — 2026-10-04

1. Task: local X TODAY prepares at most two evidence-backed candidates from real work, supports human decisions, and tracks learning.
2. Existing: local sayelf-agent-ops commit 1c9784b; RoleContract/SkillContract/Registry/IndustryPack/StateEngine; desktop SQLite bootstrap and workflow evidence utilities. Ecosystem comparison: https://github.com/langchain-ai/langgraph supports durable orchestration and interrupts, but replacing the local foundation adds a second runtime. https://docs.x.com/x-api/posts/create-post defines the sole external write API.
3. Classification: **Integrate**. Execution verdict: **GO for local implementation and offline validation**. Live account verification remains blocked pending account authorization, Public source material and API access.
4. Measurable difference: zero third-party dependencies added; zero duplicated role registries; maximum two recommendations across reruns of one date/account; invalid evidence cannot be overridden by a high quality score; approval binds exact content revision and account.
5. Success: focused tests exercise intake→selection→approval→offline connector→2/24/72h observations→hypothesis; empty day is NO_POST_RECOMMENDED. Real account adoption is a separate unverified measure.
6. Core: seven domain objects, domain daily transitions, gates, recommendation selection and learning. Shared runtime supplies local transactional state, events, task scheduling and exact approval primitives.
7. Plugins: composer, Work2Content source adapter, analytics input, Official X connector. Platform Intelligence is a Protocol only.
8. Local first: storage, scoring, evidence, draft preparation, review and metrics remain local. No model call or telemetry.
9. Classification: source material defaults Unknown; publication requires Public. Local artifacts/Internal; tokens/Sensitive. No content or token in audit summaries.
10. Public release: No. No push, PR, remote issue or upload.
11. Egress: only reviewed research search queries in this build. Connector disabled by default; future per-publication approval binds endpoint, account, content digest, revision, tool and scope. Destination api.x.com; public post retention is controlled by X and deletion is not a rollback guarantee. Missing authorization blocks execution.
12. State/check: state transitions and one-shot due tasks; no periodic polling loop. Publication schedules 2h/24h/72h analytics tasks. Missing metrics remain unavailable.
13. Epistemics: source quotes are Observations; explicit user evidence attestation can validate a Fact; composition must not invent Facts. Learning outputs Hypotheses, never causality or strategy promotion from a single post.
14. Evolution/rollback: isolated shared-base git worktree at x-growth-v03-local; original checkout untouched; local SQLite version 1; tests before promotion. Preserve data to roll back code. A live post has no guaranteed rollback.
15. WebUI Required: explicitly requested X TODAY human review. Loopback only, same-origin mutations, session CSRF token, no third-party scripts. Open→Input→Execute→Result.
16. Simplest: Python stdlib + existing Agent Ops, SQLite, HTML/JS. No new framework, cloud, OAuth server or automation daemon.
17. Not built: auto reply/DM/like/follow, trend auto-post, browser platform writes, Platform Intelligence implementation, generic AI runtime, model integration, cross-platform monitoring, account credentials, fabricated live dogfooding.

## Foundation inventory

| Capability | Observation / reuse decision |
|---|---|
| Identity/Role | RoleContract + activated role; reuse. Account authority is not implied by role identity. |
| Capability Registry | SkillContract + IndustryPack registration; reuse with X-specific pack. Registration is not execution. |
| Event Bus | Existing workflow_events is a journal, not a bus. Add transactional outbox primitive to shared runtime, delivered on explicit consumer invocation. |
| Task Queue / Scheduler | Missing; add shared one-shot due-task queue, no worker daemon. |
| State Machine | Existing StateEngine is WorkItem planning only; retain it and add configurable guarded transitions in shared runtime for domain records. |
| Memory | Existing local SQLite persistence; shared extension stores versioned namespaced records. No semantic/vector memory. |
| Evidence | Reuse canonical JSON/hash and file-integrity utilities; domain claims reference local file digest and exact supported excerpts. |
| Approval | Existing approve_and_export is specific to media ZIP export; add reusable revision-bound approval ledger, not duplicate export flow. |
| Policy | Existing role allowed_skills/forbidden_scope; reuse plus domain hard guards. |
| Audit | Existing workflow event pattern; shared extension stores digest/ID summaries atomically, not raw content. |
| Secrets | Existing Tauri system credential vault. Do not copy or read stored credentials. Python connector has injectable token provider; no token persistence; unavailable by default. |
| Observability | Existing health checks and events; shared extension exposes task/record/event counts and delivery state. No telemetry. |

Search scope: D:/Codex/skills, D:/Codex/work, Documents/Codex, user file-name inventory and root directory inventories. Three pre-existing inaccessible yaml package directories were excluded by access errors; no X-growth match was found in accessible files. No claim of exhaustive all-disk discovery.

## Implementation refinement

Quality initially required seven manual score entries. Local UI assessment showed this conflicted with the low-effort daily recommendation goal. The final local slice automatically computes a documented structural heuristic, preserving human score edits and mandatory semantic review before approval. This is an integration choice, not evidence of semantic quality or algorithm performance; acceptance retains that gap as partial. No model service or data transfer was introduced.

## Daily matching and bilingual workflow — 2026-10-04

1. Task: selecting “recommend today” prepares candidate content on demand; a local daily run also prepares available, unconsumed Agent Ops work events, matches them against read-only trend context when authorized, and presents up to two eligible recommendations plus at least two distinct draft angles when source material permits. Human approval remains mandatory.
2. Closest solutions: this repo already has the X TODAY UI, Work2Content adapter contract, local SQLite state and one-shot task queue. Agent Ops is the source of work events. Official X Trends API is the read-only trend source. Windows Task Scheduler is the native daily trigger. Ecosystem review: https://github.com/agronholm/apscheduler offers persistent Python scheduling, but would add a dependency and scheduler process for a single daily local trigger. The native daily trigger is already available: https://learn.microsoft.com/en-us/powershell/module/scheduledtasks/new-scheduledtasktrigger.
3. Classification: **Integrate**. Reuse the existing UI, state, adapter, gates, runtime and native scheduler; add no second model runtime, trend scraper, third-party package, or browser write path.
4. Measurable difference: a click completes source intake → variant generation → hard gates → recommendation; one 08:00 Tokyo local run can do the same without the browser open; candidate quota stays at two per account/day; trends never bypass evidence or human review.
5. Success evidence: tests demonstrate two distinct variants, idempotent automatic daily runs, click-triggered generation, hard-blocked unsupported/internal content, Tokyo/Worldwide read-only trend selection, and language switching. A live trend fetch and true Agent Ops producer feed are only claimed when credentials and a local producer are configured.
6. Minimum Core: persisted variant field, daily generator, read-only trends adapter, status fields, bilingual labels and a small Task Scheduler installer. Existing seven-object flow remains authoritative.
7. Boundaries: trends are context only; no trend scraping or publishing. Work2Content uses the existing event contract and local outbox. The model-free local composer adds no factual claims; actual LLM use stays out until the existing Agent Ops provider and local data boundary are wired and verified.
8. Local/data boundary: scheduler runs as the signed-in Windows user at 08:00 Tokyo time and only accesses this app's local database. X trend reads require `SAYELF_X_BEARER_TOKEN` set in the user environment; only the fixed official read endpoint receives the token. Work text and drafts stay local. No credentials are stored in SQLite or files.
9. Public release: No. All changes remain local/Internal; no GitHub transfer.
10. State/check: one daily run per account/date is idempotent; fresh source events are deduplicated; at most two drafts are prepared for the date; `BLOCKED` and `HOLD` are not eligible recommendations. Missing source/provider status is explicit.
11. Epistemics: trend names are dated external observations, never claims about why a post will perform. Work claims retain source labels and evidence requirements. Generated framing is not a new fact. Quality remains a structural heuristic, not an AI or virality prediction.
12. Evolution/rollback: installer checks for an existing task with the exact app task name and does not overwrite it. Uninstall script removes only that exact task. Code rollback leaves the local SQLite data intact.
13. WebUI: keep existing required X TODAY; add bilingual toggle and daily-run status without technical setup in the ordinary workflow. Advanced provider/scheduler details stay in local status.
14. Simplest: Python standard library, current Agent Ops adapter/runtime, official X read API, native Windows Task Scheduler.
15. Not built: remote LLM calls, Agent Ops database discovery/harvesting, browser-based platform write, auto-replies/DM/likes/follows, trend autoposting, or actual X account publishing.


## 2026-10-05 · Focused review interface
Decision: Improve. Real task: simplify the existing local daily candidate review. Closest solutions: TryPost (https://github.com/trypostit/trypost) preview and review; FeedMansion (https://github.com/makerprism/feedmansion-ai-agents) human approval queue; Postiz (https://github.com/gitroomhq/postiz-app) explicit integrations. Adopt interaction patterns only; no source copied or dependency added. Measurable difference: candidate review precedes all intake forms, settings and publication rehearsal collapse by default. Minimum core: existing HTML and existing handlers. Plugin/API boundaries unchanged; model connection remains unconfigured. WebUI is required for human selection; Open → Generate → Review remains the primary path. All data stays local/Internal; no external transfer or public release. Existing evidence/state checks and epistemic labels remain authoritative; blocked drafts cannot become recommendations through UI changes. Success evidence: live browser review of collapsed sections, generation and language switch, plus focused regression suite. Rollback: local Git revision; no database migration. Not building provider runtime, calendar, multi-platform publishing or automatic approval.

## 2026-10-05 · SAYELF brand and bilingual README
Decision: Integrate the user-supplied logo into the existing X TODAY page and README; no new product capability or dependency. Measurable result: one local PNG serves both the page brand and favicon, and the README explains the same core idea in Chinese and English. Download points to the existing public repository's default-branch source archive, which tracks the latest published `main`; this checkout has no remote and no Release exists, so local commits are not uploaded and no executable download is claimed. Data transfer/publication: none. Local changes only; retain current evidence, human-review and API safety gates. Rollback: revert the logo, page serving route, README and this record together.
