---
name: goal
description: Use when running an unsupervised work session on this repo against a task in ROADMAP.md, or when writing one. Carries the pre-flight that stops a false premise from being acted on, the time budget, and the stop conditions.
---

# Working under a goal

`/goal` is Claude Code's own command: the user types the objective inline and the
session runs until it is met. This skill is what to do while that runs.

`ROADMAP.md` is the task list — each entry has a **Done when** that is checkable
without discussion, and any method it needs. A goal usually names one (`T03`, `T14`).
There is no second file to consult: separate brief files were tried and abandoned
because one drifted into asserting a premise the work had already disproved.

First move, always: find the task in `ROADMAP.md`, read its **Done when**, and treat
that — not the prose of the goal — as the definition of finished. If the goal names no
task, write the Done-when yourself in one line and say what it is before starting.

## Pre-flight: check the premises before acting on them

Do this first, every time. In the gunboat project five goals were written from that
repo's own notes and four carried false premises; each was a reasonable reading of an
earlier note, and each was then stated as fact and acted on.

For every premise the brief lists:

1. Find the claim it rests on in `FINDINGS.md` / `FORMATS.md`.
2. Read that entry's **Evidence:** / **Verified by:** line. If it cites a byte-for-byte
   comparison or a live breakpoint, it holds. If it cites a name, a guess, or nothing,
   it does not.
3. If it does not hold, **verify it cheaply before building on it** — break on the
   routine and confirm it fires and writes what the premise says. One command, and it
   would have caught three of gunboat's four.
4. If verification fails, stop and write down what is actually true. Do not improvise a
   replacement goal — a brief whose premise died is finished; report it.

## Working

- Record as you go, not at the end. A finding goes into `FINDINGS.md` (with its
  **Evidence:** line) or `FORMATS.md` (with **Status** and **Verified by**) when it is
  established, not when the session ends.
- **Any finding that names an address also goes into `ishar.chani`** -- name, type,
  comment -- and `tools/disasm.sh` gets rerun. Prose alone means the next reader
  re-derives it. This is the step that makes the work cumulative and it is the one that
  gets skipped.
- Screenshots into `captures/<area>-<what>.png` in the same step that takes them — the
  MCP tool writes to a temp directory that gets cleared.
- New scar → `CLAUDE.md`, immediately, with the check that would have caught it.
- A reusable recipe discovered along the way → a new skill in `.claude/skills/`.
- **A question or an idea for later → a task in `ROADMAP.md`**, in that file's format,
  with a checkable Done-when. Raising it only in the reply to the user loses it: the
  chat does not survive the session and the roadmap does. That includes work that got
  cheaper or harder because of what this session found.

## Budget the user's time

The user is waiting the whole time and cannot see the tool output. Their wall clock is
the measure, not how fast the finished tool runs.

- Exploratory runs get ~30s, not the maximum that seems safe. Stop at the first
  decisive signal rather than at the configured budget.
- Reuse a running emulator; each `ish start` costs ~40s.
- Before any wait over a minute, state what it is waiting for and what will end it.
- Report progress at three minutes even mid-investigation.
- Two identical failures of one approach are enough to pivot.

## Stop conditions

Stop and report when any of these is true. Stopping is a result; grinding past one is
how a session produces confident nonsense.

- The acceptance criteria are met.
- A premise failed pre-flight (see above).
- The same approach has failed three times. Report what was tried and what was seen.
- A decision is needed that is the user's to make — scope, a destructive change, or
  anything touching files outside this repo.
- The emulator crash budget is spent: Ishar dies in the timer interrupt after a couple
  of minutes (`FINDINGS.md` §5.1). If a measurement needs a longer run than that, say
  so rather than working around it silently.

## Reporting

Tick the task in `ROADMAP.md` (`[x]`, or `[!]` with one line on the blocker) as part of
finishing, not afterwards.

End with: what was established (and its evidence), what changed on disk, what failed,
and what the next task should be. Assume the reader has not watched any of it.

# Writing a task

A roadmap entry is a title, a line or two of what and why, and a **Done when** that can
be checked without discussion. When it needs a method, put the method in the entry as an
italic paragraph — not in a separate file. Two places to describe one task means one of
them goes stale, and the stale one is the one that gets believed.

Acceptance criteria that cannot fail are the failure mode to avoid: "the listing looks
reasonable" is not a criterion, "coverage moved from X% to >Y%" is. And when an entry
rests on an earlier finding, name it, so the pre-flight above has something to check.
