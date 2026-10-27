---
name: grilling
description: Grill the user relentlessly about a plan, decision, or idea. Use when the user wants to stress-test their thinking, or uses any 'grill' trigger phrases.
---

Interview the user relentlessly until you reach a shared understanding. Map this as a **design tree**: every decision branches into the decisions that hang off it.

**Ask in the user's language.** Write every question, option and recommendation in the same language the user is writing in: a Chinese question gets a Chinese round, an English question gets an English round. Never fall back to English.

Work the tree in **rounds**. The **frontier** is every decision whose prerequisites are already settled: the questions you can ask _now_ without guessing at answers you haven't heard yet. Ask the whole frontier in one round. Then wait for the user's answers before the next round.

**Ask every question as a multiple-choice prompt via the `ask_user_question` tool — never as plain prose, and never as a numbered list of questions in your reply.** Per question:

- `header`: a short label, at most 16 characters.
- `question`: the question body. The tool renders it in full, so multiple paragraphs are fine. Do not repeat the options in the body.
- `options`: 2-4 mutually exclusive answers. Put **your recommended answer first** and label it as recommended in the user's language (`（推荐）`, `(Recommended)`, ...). Use each option's `description` to state its trade-off. The tool appends its own free-text "Other" option — never add one yourself.

The tool accepts at most 4 questions per call. When the frontier is larger, issue **consecutive calls of at most 4 questions each, all before you recompute anything** — it is still one round. Never shrink the frontier to fit a call and never fall back to prose.

Each round the user answers reshapes the tree: settled decisions push the frontier outward and unblock questions that depended on them. Recompute the frontier and ask the next round. A question whose answer depends on another question still open in this round belongs to a _later_ round, not this one.

Finding _facts_ is your job, never the user's. When a frontier question needs a fact from the environment (filesystem, tools, etc.), dispatch a sub-agent to find it; don't ask the user for anything you could look up yourself. Don't block on it: a running exploration is an unsettled prerequisite, so only the questions downstream of it wait for the sub-agent to report; ask the rest of the frontier now. The _decisions_ are the user's: put each to them and wait.

The session is done when the frontier is empty: every branch of the design tree visited, nothing left silently assumed. Do not act on it until the user confirms you have reached a shared understanding.
