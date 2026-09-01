# Community Research — Competitor Scan & the pi Agent Study

> Date: 2026-09-01 · Purpose: ground the audit (`AUDIT_REPORT.md`) and the
> target architecture (`ARCHITECTURE_AND_PLAN.md`) in what the ecosystem
> actually does. Part I covers comparable projects; Part II studies the pi
> coding agent as an architecture reference. All sources cited.

## Part I — Competitor scan

LoveRiskEngine's position: **local-first, zero-runtime-dependency,
evidence-first relationship decision support — with risk detection but no
judging tone.** The scan covered four camps; the headline finding is that the
intersection is unoccupied.

### The four camps (and why each is incomplete)

| Camp | Examples | What they do | What they lack |
|---|---|---|---|
| Relationship "remember" tools | Tilly, Nametag, Monica, Bonds | capture interactions, reminders, notes | no risk/signal detection |
| Abuse "detect" tools | Texts with My Ex, Red Flags Detector, myPlan | flag manipulation/abuse patterns | cloud upload of private chats, opaque thresholds, red-flag alarm framing |
| Mental-health "screen" tools | MindWell | transparent non-diagnostic screening | general mental health, web, no relationship-risk dimension, not a CLI |
| Decision "record" tools | adr-tools, vrdx, log-decisions | append-only decision logs | cold/professional framing, software decisions only |

**Differentiation:** the "detect" camp requires uploading private
conversations and hides its thresholds; the "remember" camp has no detection
at all. Local + transparent + non-judging risk detection is open ground.

### A. Relationship journals / boundary tools

| Project | URL | License | Verdict for us |
|---|---|---|---|
| Tilly | https://github.com/carlassmann/tilly (https://tilly.social) | MIT | Partial adopt: "people-first" modeling, offline-first; **avoid** cloud auth (Clerk) + cloud LLM (Gemini) |
| Nametag | https://github.com/mattogodoy/nametag (https://nametag.one) | AGPL-3.0 | Adopt data model: typed relationships + interaction journal + network view; no detection dimension |

### B. Personal CRM

| Project | URL | License | Verdict for us |
|---|---|---|---|
| Monica | https://github.com/monicahq/monica | AGPL-3.0 | Adopt schema ideas (contacts/activities/reminders); avoid its heavyweight full-stack scope |
| **Bonds** ⭐ | https://github.com/naiba/bonds | BSL 1.1 (source-available) | **Adopt the engineering shape** (SQLite + single binary + local-first + mood recording + **"needs-verification" data-freshness flag** + built-in MCP endpoint); avoid the BSL license and record-only positioning |
| Nextcloud Contacts | https://github.com/nextcloud/contacts | AGPL-3.0 | Reference only (sovereign self-hosting as direction); thin data model |

Bonds is the closest engineering sibling: SQLite, single binary, local-first,
and — most interestingly — a *"needs-verification"* flag that marks data as
possibly stale. That maps directly onto our "observation ≠ interpretation,
record alternative explanations" stance: **freshness self-checks are the
engineering form of evidence-first.** (Noted for the verification-checklist
roadmap item.)

### C. Decision journals / decision-support CLIs

| Project | URL | License | Verdict for us |
|---|---|---|---|
| adr-tools | https://github.com/npryce/adr-tools | MIT | Adopt the **`supersedes` link** — the same semantics as our "boundaries retire, never delete" |
| vrdx | https://github.com/niklas-heer/vrdx | unclear (verify) | Adopt "decision = status + context + consequences" metadata shape |
| **log-decisions** ⭐ | https://github.com/swe-workflow/log-decisions | MIT | **Strongest adopt**: append-only `DECISIONS.md`, `Supersedes:`, and the decide/assume/**escalate** 2×2 — "escalate" is exactly our "the engine never convicts; the user decides" |

The log-decisions pattern is the closest mature practice to our philosophy in
the wild: append-only records, explicit supersession, and a hard rule that
irreversible/high-stakes calls escalate to a human review queue. Its
decide/assume/escalate matrix is a ready-made UX skeleton for "signal →
transparent presentation → user adjudication."

*(Note: no "jd journaling daemon" exists as such; `jdd` is the Johnny Decimal
file-organizing daemon — unrelated.)*

### D. Mood / abuse-pattern trackers

| Project | URL | License | Verdict for us |
|---|---|---|---|
| **MindWell** ⭐ | https://github.com/rudra496/mindwell | MIT | **Adopt the framing**: public, non-diagnostic screening instruments + explicit "this is not a diagnosis" boundary + calm tone |
| Texts with My Ex | https://www.producthunt.com/products/texts-with-my-ex | commercial | The mirror to avoid: cloud upload of private chats, opaque AI flags, alarmist framing |
| Red Flags Detector: Texting | https://apps.apple.com/us/app/red-flags-detector-texting/id6630375062 | commercial | Same mirror |
| myPlan | https://myplanapp.org | non-OSS | Partial adopt: safety-planning/precommitment mechanics; avoid the "push the user to act" tone |

MindWell proves the product route we chose — public, explainable, non-diagnostic
rules instead of black-box AI verdicts — and pairs it with a calm, non-judging
voice. Texts with My Ex is the anti-model: it shows the pain (detection is
valuable) and the failure (privacy upload, opaque thresholds, alarm framing).
Our cooldown/precommitment guardrails and exit-cost ordinals are the myPlan
mechanic without its rescue-agency tone.

### The three concrete practices worth borrowing

1. **Bonds' `needs-verification` freshness flag + SQLite/single-binary local
   shape** — feeds the mutual-verification-checklist roadmap item.
2. **log-decisions' append-only + `Supersedes:` + decide/assume/escalate with a
   human review queue** — feeds the decision-UX design and formalizes our
   retire-not-delete semantics.
3. **MindWell's public non-diagnostic instruments + explicit boundary
   statement** — feeds how we document every detector as an explainable,
   non-diagnostic rule.

## Part II — The pi agent study

*(Local check: `~/.pi` does not exist on this machine, so this study rests on
authoritative online sources — official README/docs, npm registry, and two
independent architecture analyses. No secrets were read.)*

### What pi is

- **pi** (formerly `badlogic/pi-mono`, now `earendil-works/pi`; npm
  `@earendil-works/pi-coding-agent`, latest 0.84.4) — MIT, TypeScript
  monorepo, by Mario Zechner (libGDX) and now maintained by earendil-works
  (Armin Ronacher involved). A **minimal, controlled terminal coding-agent
  runtime**: four tools by default (`read/write/edit/bash`), and everything
  else — skills, slash-commands, extensions — assembled on demand.
- Repos: https://github.com/earendil-works/pi · https://github.com/badlogic/pi-mono
- npm: https://www.npmjs.com/package/@earendil-works/pi-coding-agent
- Design essays: https://mariozechner.at/posts/2025-11-30-pi-coding-agent/ ·
  https://mariozechner.at/posts/2025-11-02-what-if-you-dont-need-mcp/

### The architectural decisions that matter to us

1. **The session *is* the file.** One append-only JSONL tree per session
   (`id`/`parentId`), stored under `~/.pi/agent/sessions/--<cwd>--/<ts>_<uuid>.jsonl`.
   Versioned format (v1→v3) with load-time migration; `/tree`, `/fork`,
   `/clone`, `/compact`; compaction is lossy **but full history stays in the
   file**. Everything is serializable, replayable, hand-off-able across
   providers.
2. **Assets as versioned text files.** `prompts/*.md` (frontmatter +
   positional args, filename = command name), `skills/<skill>/SKILL.md`
   (Agent Skills standard, progressive disclosure: name+description in
   context, body loaded on demand), `SYSTEM.md` (replace) /
   `APPEND_SYSTEM.md` (append) / `AGENTS.md` (walked up from cwd).
3. **Minimal tool surface + two extension surfaces + event hooks.**
   `registerTool` (LLM-visible) vs `registerCommand`/UI (user-visible, not in
   context); first-class `on("tool_call")` handlers for audit/gating. No MCP
   by deliberate design (mutable tool surfaces break MCP's cached-prefix
   assumption); CLI+README or a bridge extension instead.
4. **Config layering + trust + read-only default.** Global
   `~/.pi/agent/` vs project `.pi/`; `defaultProjectTrust: ask/always/never`;
   per-asset `--no-extensions` / `--no-skills` / … switches; a one-liner
   read-only mode (`pi --tools read,grep,find,ls`). Security is explicit:
   third-party skills/packages run arbitrary code — stated plainly.

### Adopt / skip for LoveRiskEngine

**Adopt (recorded in `ARCHITECTURE_AND_PLAN.md` §3/§5):**

- data home + versioned text assets (profiles, boundaries, docs as files);
- minimal tool surface + audit hooks if the engine is ever consumed by agents;
- global/project layering, trust gate, read-only default as the agent-facing
  safety baseline;
- honest security disclosures (never imply a plugin is sandboxed when it is not).

**Skip:**

- the "no MCP / no subagents / no plan mode" absolutism (right for a minimal
  runtime, not a product surface);
- lossy auto-compaction (audit integrity outranks token savings for a
  decision engine — our data is append-only, period);
- TypeScript/TypeBox specifics (concepts port to Python, the stack doesn't).

### The three most valuable pi lessons

1. Assets and sessions as **readable, versionable, event-sourced text files**.
2. **Minimal tool surface + two extension surfaces + `on(tool_call)` audit
   hooks** — the shape of "engine as an agent tool" without losing control.
3. **Global-vs-project config + trust gate + read-only default + per-asset
   opt-outs** — the risk isolation baseline for agent-driven use.

## Part III — How the findings landed

- Freshness self-check (Bonds) → mutual verification checklist (roadmap #3).
- Append-only + supersede + escalate-to-user (log-decisions/adr-tools) →
  our retire-not-delete semantics and the decision-UX design.
- Public non-diagnostic instruments + boundary statement (MindWell) → how
  every detector documents itself as an explainable, non-diagnostic rule.
- pi's file-as-truth + permission layering → `ARCHITECTURE_AND_PLAN.md` §3
  (data home, lossless export) and §5 (agent-integration gate).
