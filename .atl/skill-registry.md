# Skill Registry

**Delegator use only.** Any agent that launches sub-agents reads this registry to resolve compact rules, then injects them directly into sub-agent prompts. Sub-agents do NOT read this registry or individual SKILL.md files.

See `_shared/skill-resolver.md` for the full resolution protocol.

## User Skills

| Trigger | Skill | Path |
|---------|-------|------|
| creating, opening, or preparing PRs for review. | branch-pr | C:\Users\Usuario\.gemini\config\skills\branch-pr\SKILL.md |
| PRs over 400 lines, stacked PRs, review slices. | chained-pr | C:\Users\Usuario\.gemini\config\skills\chained-pr\SKILL.md |
| writing guides, READMEs, RFCs, onboarding, architecture, or review-facing docs. | cognitive-doc-design | C:\Users\Usuario\.gemini\config\skills\cognitive-doc-design\SKILL.md |
| PR feedback, issue replies, reviews, Slack messages, or GitHub comments. | comment-writer | C:\Users\Usuario\.gemini\config\skills\comment-writer\SKILL.md |
| build web components, pages, artifacts, posters, dashboards, React components, HTML/CSS layouts, or when styling/beautifying any web UI. | frontend-design | C:\Users\Usuario\.gemini\config\skills\frontend-design\SKILL.md |
| Go tests, go test coverage, Bubbletea teatest, golden files. | go-testing | C:\Users\Usuario\.gemini\config\skills\go-testing\SKILL.md |
| creating GitHub issues, bug reports, or feature requests. | issue-creation | C:\Users\Usuario\.gemini\config\skills\issue-creation\SKILL.md |
| judgment day, dual review, adversarial review, juzgar. | judgment-day | C:\Users\Usuario\.gemini\config\skills\judgment-day\SKILL.md |
| new skills, agent instructions, documenting AI usage patterns. | skill-creator | C:\Users\Usuario\.gemini\config\skills\skill-creator\SKILL.md |
| implementation, commit splitting, chained PRs, or keeping tests and docs with code. | work-unit-commits | C:\Users\Usuario\.gemini\config\skills\work-unit-commits\SKILL.md |

## Compact Rules

Pre-digested rules per skill. Delegators copy matching blocks into sub-agent prompts as `## Project Standards (auto-resolved)`.

### branch-pr
- Every PR MUST link an approved issue (`Closes #N`, `Fixes #N`, `Resolves #N`).
- The linked issue MUST have the `status:approved` label.
- Every PR MUST have exactly one `type:*` label (e.g., `type:bug`, `type:feature`).
- Branch names MUST match: `^(feat|fix|chore|docs|style|refactor|perf|test|build|ci|revert)\/[a-z0-9._-]+$`.
- Commit messages MUST match Conventional Commits format (`type(scope): description`).
- Automated checks must pass before merging.

### chained-pr
- Split PRs over 400 changed lines unless a maintainer explicitly accepts `size:exception`.
- Keep each PR reviewable in about ≤60 minutes.
- Use one deliverable work unit per PR; keep tests/docs with the unit they verify.
- State start, end, prior dependencies, follow-up work, and out-of-scope items in every chained PR.
- Every child PR must include a dependency diagram marking the current PR with `📍`.
- Feature Branch Chain: draft/no-merge tracker PR; child #1 targets tracker, subsequent children target immediate parent.
- Do not mix chain strategies once chosen.

### cognitive-doc-design
- Lead with the answer: put decisions, actions, or outcomes first; context after.
- Progressive disclosure: start with the happy path, then add details and edge cases.
- Chunking: group information into small sections and keep lists short.
- Recognition over recall: prefer tables, checklists, examples, and templates over prose.
- PR documentation: state what to review first, out of scope, chain links, and checklists.

### comment-writer
- Be useful fast: start with the actionable point; keep comments to 1-3 short paragraphs.
- Be warm and direct, sounding like a teammate, not a corporate bot.
- Explain the technical reason when asking for a change.
- Match thread language: if Spanish, use Rioplatense Spanish/voseo (`podés`, `tenés`, `fijate`, `dale`).
- No em dashes; use commas, periods, or parentheses instead.

### frontend-design
- No generic AI design slop (avoid pure #000, solid purple-to-pink gradients, standard Inter-font).
- Ensure strict accessibility (WCAG 2.1 AA with contrast ratios >= 4.5:1).
- Declare design tokens (colors, spacing, typography) as CSS variables in `index.css` or equivalent.
- Choose unique typography (e.g., Google Fonts for headers) and pair with a clean body font.

### go-testing
- Prefer table-driven tests for multiple cases; use `t.Run()`.
- Test behavior and state transitions, not implementation details.
- Use `t.TempDir()` for filesystem tests; never use a real home directory.
- Keep integration tests skippable using `testing.Short()`.
- For Bubbletea, test `Model.Update()` directly; use `teatest` only for interactive flows.
- Golden files must be deterministic and updated only via `-update`.

### issue-creation
- Blank issues are disabled; must use a template (bug report or feature request).
- New issues automatically get `status:needs-review`.
- A maintainer must add `status:approved` before any PR can be opened.
- Direct questions to Discussions instead of issues.

### judgment-day
- Resolve project skills and inject `Project Standards` into judge/fix prompts.
- Launch two blind judges in parallel concurrently; never review the code yourself.
- Wait for both judges; never accept partial verdicts.
- Classify warnings as `WARNING (real)` only if normal use triggers them; else downgrade to INFO.
- Ask user before fixing Round 1 confirmed issues.
- Re-judge in parallel after fixes; terminal states are only `APPROVED` or `ESCALATED`.

### skill-creator
- Follow `docs/skill-style-guide.md` first, or inline fallback rules.
- Skill is a runtime instruction contract for an LLM, not human documentation.
- Quoted, trigger-first description on one physical line (<=250 chars).
- Target 180-450 body tokens; put templates in `assets/` and conceptual detail in `references/`.
- Use required structure: Activation Contract, Hard Rules, Decision Gates, Execution Steps, Output Contract, References.

### work-unit-commits
- Commit by work unit (deliverable behavior, fix, migration, or docs).
- Do not commit by file type (avoid adding models, then services, then tests separately).
- Keep tests and docs in the same commit as the behavior they verify/explain.
- Storytelling: commits should show outcome and purpose clearly.
- Monitor changed lines to prevent PRs exceeding 400 lines (use chained PRs).

## Project Conventions

| File | Path | Notes |
|------|------|-------|

Read the convention files listed above for project-specific patterns and rules. All referenced paths have been extracted — no need to read index files to discover more.
