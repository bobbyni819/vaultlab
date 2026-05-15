# Goal: Public testimony channel (sub-goal 3.3 of north-star plan)

**Status:** ✅ LANDED (with one manual residual — see below).
**Date completed:** 2026-05-15
**Parent spec:** `.claude/goals/vaultlab-north-star.md` Criterion #1.
**Prior sub-goal:** 3.2 (commit `b4b3ca4`) — README link + testimony issue template.

## Why

North-star Criterion #1 ("first unsolicited real-use testimony") needs a public landing channel. README already points at GitHub Discussions, but Discussions had not been enabled repo-side. This sub-goal flips that switch and seeds a welcome thread so the link doesn't 404 and visitors have a clear primer on what to share.

## What landed

1. **GitHub Discussions enabled** on `bobbyni819/vaultlab` via
   `gh api -X PATCH /repos/bobbyni819/vaultlab -f has_discussions=true`.
   Verified: `gh api /repos/bobbyni819/vaultlab --jq '.has_discussions'` → `true`.

2. **Welcome thread published** as discussion #1 in the Announcements category:
   - URL: https://github.com/bobbyni819/vaultlab/discussions/1
   - Title: `Welcome — tell us how you used vaultlab`
   - Body covers: what to share (testimonies, workflow Qs, feature requests + use cases), what to file as issues instead (bugs, primitive requests, formal testimonies), maintainer cadence.
   - Created via GraphQL `createDiscussion` mutation against
     `repositoryId: R_kgDOSPDcgQ`, `categoryId: DIC_kwDOSPDcgc4C9ICE` (Announcements).

3. **Strategic spec EVIDENCE updated** — Criterion #1 line in `.claude/goals/vaultlab-north-star.md` now reads:
   > 🟡 Criterion #1 (adoption signal): channel LIVE at https://github.com/bobbyni819/vaultlab/discussions — welcome thread #1 published inviting testimonies (Announcements category). Awaiting first non-Bobby contribution.

4. **KB mirror** at `G:/My Drive/Knowledge/vaultlab/Sources/Notes/vaultlab-north-star-2026-05-14.md` updated to match.

## What did NOT land (manual residual)

**Pinning the welcome thread.** GitHub's public GraphQL API does not expose a mutation to pin discussions, despite the `PinnedDiscussion` type being queryable. The schema check ran:

```
gh api graphql -f query='{ __schema { mutationType { fields { name } } } }' \
  --jq '.data.__schema.mutationType.fields[].name' | Select-String -Pattern '(?i)pin'
```

Returns only `pinEnvironment`, `pinIssue`, `pinIssueComment` — no `pinDiscussion`. This is a known GitHub limitation as of the API version available 2026-05-15.

**Bobby action required (~10 seconds):**
1. Visit https://github.com/bobbyni819/vaultlab/discussions/1
2. Click the gear/`...` menu → **Pin discussion**

That's it. Once pinned, the EVIDENCE line in the strategic spec can be tightened (drop the pinning caveat).

## Verification commands re-run before commit

```powershell
gh api /repos/bobbyni819/vaultlab --jq '.has_discussions'
# → true

gh api graphql -f query='{ repository(owner:"bobbyni819", name:"vaultlab") { discussions(first: 5) { nodes { title url number } } } }' \
  --jq '.data.repository.discussions.nodes'
# → [{"number":1,"title":"Welcome — tell us how you used vaultlab","url":"https://github.com/bobbyni819/vaultlab/discussions/1"}]
```

## Files touched (this sub-goal only)

- `.claude/goals/vaultlab-north-star.md` — EVIDENCE Criterion #1 line updated.
- `.claude/goals/public-testimony-channel.md` — this file (new).
- KB mirror: `G:/My Drive/Knowledge/vaultlab/Sources/Notes/vaultlab-north-star-2026-05-14.md`.

No source code touched.

## Decision log

- **Category choice:** Announcements (not General). Welcome threads are announcement-style and the category appears first in the sidebar, maximizing visibility for new visitors.
- **Pinning via UI vs blocking on it:** chose to land the channel + thread now and leave pinning as a 10-second manual residual rather than waiting for a GitHub API change. The thread is the first (and currently only) discussion, so it's already at the top of the list — pinning is cosmetic stickiness, not gating.
