Interview Bobby relentlessly about every aspect of the plan until you both reach a shared design concept. Walk down each branch of the design tree, resolving dependencies between decisions one by one.

Inspired by Matt Pocock's `/grill-me` skill from "Claude Code for real engineers." The point is to surface the implicit design concept that exists between the user and the AI before any code is written, so the implementation matches what the user actually wants — not what the AI guessed they meant.

## When to use

- Before implementing any non-trivial feature or refactor
- When Bobby says "let's build X" and X has more than one sensible interpretation
- When you find yourself making assumptions about scope, behavior, or edge cases
- When Bobby explicitly invokes `/grill-me`

## The interview

Ask Bobby questions one at a time (or 2-3 at most per turn). Do NOT batch 20 questions at once. The interview is a conversation, not a form.

Cover at minimum:

**1. The user's mental model**
- What problem are you actually trying to solve? (Often different from the feature description.)
- Who else uses this — just you, or other people?
- What's the success criterion you'd judge it by?
- What's the worst-case failure mode you want to avoid?

**2. Scope and boundaries**
- Is this a one-off or recurring need?
- Does it need to work on Windows only, or all your machines?
- Does it need to be portable across the bobby-tools monorepo, or specific to one project?
- Does it integrate with existing systems (KB, dashboard, slash commands), or stand alone?

**3. Behavior and edge cases**
- What should happen when [obvious failure case]?
- Is [hidden assumption] correct?
- Walk through a concrete example: "If I do X, what should you see?"
- What happens when nothing matches / the input is empty / the network is down?

**4. UI and interaction**
- CLI, web, or both?
- Default behavior vs explicit invocation?
- How should errors surface to you?
- What's the rollback / undo path if it does the wrong thing?

**5. Storage and persistence**
- Does state need to survive a restart? Across machines?
- Where should config / data live (`~/.config/`, KB, repo, Google Drive)?
- Is anything sensitive that should NOT go in git?

**6. Integration with existing tools**
- Should this become a slash command, a Python module, both?
- Does it need to extend an existing skill (`/kb`, `/research-pipeline`, etc.)?
- Should the output go into the KB? The Google Doc work log?

## How to behave during the grill

- Be adversarial. Push back on vague answers. "What does 'it should be smart' mean concretely?"
- Walk down each branch. If Bobby answers "yes" to something, follow up: "Then how should X work when Y?"
- Surface dependencies. If decision A constrains decision B, name it: "If we go with X, we won't be able to do Y later — is that OK?"
- Don't propose solutions yet. Your job is to extract requirements, not implement.
- Keep going until you can confidently restate the entire feature in 3-5 bullets and Bobby agrees with all of them.

## Termination

When you think you're done, write a "shared understanding" summary as a numbered list of decisions made, and ask Bobby: "Is this the design? Anything missing?"

Only after Bobby confirms, proceed to implementation (or write a PRD / plan, depending on size).

## Anti-patterns (avoid these)

- Asking 30 questions at once
- Asking yes/no questions when open-ended would surface more
- Stopping after 3 questions because "it seems clear"
- Letting Bobby off the hook when an answer is vague
- Jumping to implementation in the middle of the interview
