# Working on this repo

Reverse engineering *Ishar: Legend of the Fortress* (Silmarils, 1992) toward a Compose
Multiplatform rewrite. The game files are not ours to commit.

Skills carry the recipes (`.claude/skills/`). This file carries the scars: the mistakes
already made here, and the check that would have caught each one. Add to it the moment
something goes wrong — the entry is worth least when you finally remember to write it.

## Where things go

| what | where |
|---|---|
| game mechanics, world, content | `FINDINGS.md` |
| byte layouts, file formats | `FORMATS.md` |
| reference screenshots | `captures/<area>-<what>.png`, linked from the findings section they illustrate |
| plans, task breakdowns | Vault: `Projects/Ishar/reverse-engineering-plan/` |
| the task list | `ROADMAP.md` — checkable tasks with their method, ticked as they land |
| annotations | `stub.chani`, `ishar.chani` (when they exist) |
| generated listings | `ishar-listing.txt` — output, never edited by hand |

Every finding carries an **Evidence:** line saying how it was established. Every format
carries **Status** and **Verified by**. A claim with neither is a guess, and six weeks
later it will be read as a fact.

## A rule with no trigger gets walked past

Everything that went wrong in the session that produced this file was already written
down somewhere in it. Better wording would not have helped; three attempts at the same
approach, twenty-seven minutes of unreported waiting, and a database that had not moved
since T05 all happened with the rules sitting right there.

What made them bite was one of two things, and it is worth reaching for these before
writing another paragraph:

- **Mechanical enforcement.** `tools/timebox 30 <command>` kills at the cap. A default
  buried in a script gets forgotten; a cap you have to type gets noticed.
- **A step at the moment it applies.** "Record findings as you go" changed nothing until
  the `goal` skill's Reporting section ended with *sweep the roadmap for what this
  revealed*. The rule says where; the step says when.

So when a rule keeps being broken, do not rewrite it. Ask where in the work it should
have fired, and put it there — or make a tool refuse.

## The rule that matters most

**A check that cannot distinguish a right answer from a wrong one is not a check.**
Borrowed from the gunboat work, where the first unpacker zero-filled 64 KB of the
program and the image still booted, still ran for 80 seconds, and still disassembled as
clean startup code at the entry point. Two cheap checks passed on a third of a game.
For anything reconstructed — an unpacker, an asset decoder — the check is a byte-for-byte
comparison against what the emulator actually holds.

## Future work goes in ROADMAP.md, not in the chat

The conversation is volatile: a good idea raised there is gone by the next session, and
"we should look at X" in a reply to the user has no reader afterwards. `ROADMAP.md` is
the only place that survives.

So anything that is work-not-yet-done goes in it, in the format already there:

```
- [ ] **T09d · Why the scancode table differs on disk and in memory**
      One or two lines of what and why, with the addresses already known.
      **Done when:** something a machine or a stranger can check.
```

That includes all of:

- **New questions found while doing something else.** Most of M2's tasks came from
  noticing things mid-trace -- a setup screen in a buffer, a table that reads
  differently on disk than in memory. Those were nearly lost to the chat.
- **Work that got cheaper or harder.** When T07 located the asset path, T10 stopped
  being a search; that belongs in the entry, not only in a reply.
- **Blockers**, as `[!]` with one line on what blocks it and what to try next.
- **Anything suggested to the user as a "next step".** If it is worth proposing, it is
  worth a line in the roadmap first -- otherwise the proposal is the only record and it
  dies with the session.

Status ticks alone are not enough. Keeping `[x]`/`[~]`/`[!]` current while never adding
what was discovered leaves the roadmap describing yesterday's plan, which is what
happened through all of M2 until the user asked.

## A finding with an address goes into the database, not just into prose

`ishar.chani` is the durable artefact. `ishar-listing.txt` is disposable output
regenerated from it, and `FINDINGS.md` is for people. A name written only in prose has
to be re-derived by whoever next reads the listing; a name in the database shows up
everywhere the address is used -- annotating `scancode_to_char` at `seg_0000:04be` turned
an anonymous `mov al,[bx+4be]` in the ISR into `mov al, scancode_to_char[bx]`, for free,
in every routine that touches it.

So: **whenever a finding names an address, annotate it in the same step that records
it.** Routine, table, flag, call site -- name it, type it, comment it, rerun
`tools/disasm.sh`. This was skipped for the whole of M2 until the user asked why the
database had not moved since T05.

## Coverage is not comprehension

`tools/disasm.sh` prints the share of code bytes chani decoded into instructions instead
of leaving as `db`. That is all it measures: whether the disassembler knows where an
instruction starts. It says nothing about whether anyone knows what the code does.

At 38.1% coverage this project had roughly 370 annotations, of which about thirty name a
routine and mean something. Combat, magic, character classes and quest logic had not been
located at all. The number moves when a seed is imported from an execution trace, which
costs nothing in understanding.

Quote it as "38.1% of the code decodes as instructions", never as "we understand a third
of the game". The honest measures of understanding are the ones in FINDINGS.md and
FORMATS.md: a format is understood when a decoder reproduces the emulator's bytes, and a
routine is understood when a prediction made from it survives a check.

## The clock that counts is the user's

A tool that answers in 7 seconds after 27 minutes of restarts, expired budgets and dead
ends took 27 minutes. Report the wall time from the request to the result, not the
benchmark of the last run, and never present a tool-speed win as if it were time the
user got back.

Rules that follow from it, all of them violated in the session that produced this
section:

- **Cap an exploratory run at the answer, not at the budget.** Two traces were left to
  run out 240s and 300s after the first 20 seconds had shown the pattern. Default to
  ~30s for anything exploratory; raise it only for a run whose length is the point.
- **Reuse the emulator.** `ish start` is ~40s. Eight restarts went on experiments that
  could have shared one instance. Restarting is a cost to count, not a reflex.
- **Say what a long wait is for, before it starts.** If a run will take more than a
  minute, name what it is waiting for and what ends it. "Tracing to the language menu,
  stops at the first `logo.IO` open or 60s" is a contract; silence is not.
- **Report at three minutes.** If nothing has been shown to the user in that long, stop
  and say where things are, even mid-investigation. They cannot see the tool output.
- **Put exploratory runs under `tools/timebox`.** `tools/timebox 30 <command>` kills at
  the cap and prints what it cost. A cap that has to be typed is a cap that gets
  noticed; a default buried in a script is one that gets forgotten.
- **Pivot on the second failure, not the third.** Four variants of GDB-side conditions
  were tried after the second had already settled it. The stop rule says three; two is
  usually enough when the failures look identical.

## Scars

### Killing the emulator with `timeout` leaves it running

`run.sh` runs `dotnet run`, which spawns the emulator as a child. `timeout` and
`pkill -f run.sh` kill the wrapper; the child keeps the MCP, GDB and HTTP ports. The
next launch then dies inside Kestrel with a stack trace that reads like a new bug, and
three sessions were wasted on that before it was recognised.

Kill by matching the emulator itself (`pkill -f "McpHttpPort <port>"`), then confirm
with `ps` and `lsof` before relaunching. `run.sh` picks free ports automatically; a
*pinned* `MCP_PORT`/`HTTP_PORT`/`GDB_PORT` skips that, which is why it now fails with a
clear message instead of a Kestrel trace.

### "Enqueued while paused" does not mean the emulator is paused

`send_keyboard_key` reports `Keyboard event enqueued while paused` in circumstances
where `resume_emulator` immediately answers `Already running`. It was read as "the
emulator is paused, that's why the key does nothing", and sent the investigation the
wrong way for a while. The key was being delivered the whole time.

To know whether the machine is running, sample `read_cpu_state` twice and compare
`Cycles`. Do not infer it from a tool's prose.

### A still screen is not a hung screen

With the CFG reload enabled, the game sat black for two minutes after language
selection and was reported as stuck. It was the intro playing. Cycles were advancing
the entire time and that was already visible in the samples taken.

Before calling anything hung: cycles advancing? screen actually static across two
screenshots a while apart? known timing for this phase? Ishar's intro is minutes long
and mostly dark.

### A plausible cause is not a cause

Spice86 reloads a CFG graph dumped by earlier runs by default, and a stale graph in a
game that relocates code between runs is an excellent story for a crash. It was
reported as the likely cause and the default was changed on the strength of it. The
A/B — same session driven twice, reload on and off — showed no difference: ~455 moves
of play, no crash either way.

Run the A/B before recommending the change, not after. The flag stays off as hygiene,
which is a different and much weaker claim.

### Keys need a down *and* an up

`send_keyboard_key` takes `isPressed`. One call is half a keypress; the game may see a
key held forever, or nothing at all. Always send `true` then `false`.

### Screenshots die in a temp directory

The MCP `screenshot` tool writes to a system temp folder that is cleared without
warning. Copy anything worth keeping into `captures/` with a real name in the same
step that takes it — not later.

### chani: where an annotation goes decides whether it exists

An `attr[...]` inside a `file[...]` or `segment[...]` block is ignored with no warning;
after the project's final `end` it is a parse error. Insert before the project's
closing `end` — that is what a `tools/note` equivalent is for, once it exists. And
`data` is not a type: unrecognised names are read as struct names, so the error says
`unknown struct 'data'`, which does not read like a bad type at all. Use `u8`.

### Read the branch before transcribing the routine

`tools/io.py` was written from the RLE decoder at `seg_0000:7a79`, which is real, well
annotated, and used by nine of the game's 106 assets. Four instructions earlier there is
a test on the mode byte that sends the other 97 somewhere else entirely — to a
bit-packed LZ decoder that copies part of the stream into its own code.

The port failed on the files that matter and produced plausible-looking output for the
rest. Before transcribing a routine, walk backwards to whatever chose it and check which
inputs actually arrive there — and prefer ground truth captured from the machine, which
is what showed the output could not possibly have come from the code being read.

### A routine you found by reading is not the routine in use

T10 located an RLE decoder with a refill helper by reading the listing, annotated it,
and wrote it up. A breakpoint on it never fired during a boot that demonstrably loads
the file. There were three near-identical copies of the same helper, and the two the
game actually uses are elsewhere — named only once the tracer read one word past the
interrupt frame to get the *outer* caller.

Static reading proposes; the machine disposes. Before writing up a routine as "the"
anything, break on it and see it fire — and if a breakpoint on the obvious candidate
does not fire during an operation that must use it, that is the finding, not a
malfunction.

### `ss:` and `cs:` variables are not offsets in the code segment

Eight variables were annotated at `seg_0000:2480`, `seg_0000:0b04` and friends because
that is how they read in the listing — `mov cx, ss:[2480h]`. They are DGROUP offsets:
SS is `load + 0x0c0b` at runtime, so `ss:2480` is image `0x0c0b0 + 0x2480`, which lands
in `seg_0941`. The annotations typed *code bytes* in `seg_0000` as data.

The tell was coverage going **down**, 32.0% to 31.6%, after adding annotations that only
add information. A number moving the wrong way is the thing to look at, not the thing to
round off.

To place one: get the segment register's runtime value (traces show `SS = 0d88`,
`DS`/`CS` vary), subtract `load`, and check the paragraph against the data-only list
`tools/segmap.py` prints — `0x0c0b` is on it, which is the corroboration that it is
DGROUP and not a coincidence. `cs:`-relative variables inside a routine are the easy
case: they belong to that routine's own segment.

### chani loads the FILE, so segment ranges carry the MZ header

`tools/segmap.py` emitted `load = [0..]:exe[0x00000..0x09410]` using *image* offsets,
but chani reads the whole file -- 592 bytes of MZ header included -- so the entire
listing sat 0x250 bytes off. Every address in it named the wrong byte, and nothing
complained: the disassembly still looked like code, the annotations still attached,
coverage still rose, and one of them even rendered `mov al, scancode_to_char[bx]`
convincingly.

It surfaced only because a call site traced live as `mov bx,ss:[0bbe] / mov ah,3f /
int 21h` came back from the listing as `call [0e97:0000]`. **Cross-check the listing
against bytes you obtained another way before trusting an address**: dump the same
offset from the image and from the emulator's memory and see that all three agree.

It also produced a false finding: `scancode_to_char` was recorded as differing between
disk and memory, and a roadmap task written to explain the discrepancy. There was no
discrepancy. A difference between two sources is a bug in the reader until proven
otherwise.

### chani takes `//` comments, not `#` or `;`

`#` is a parse error pointing at the comment line, which reads like a problem with the
line *after* it. `;` is worse: `tools/segmap.py` was ported from gunboat still emitting
`;` and the generated database failed to parse. Only `//` works.

### chani panics on some code seeds, and the panic names nothing

`layout.rs:361 unreachable!` fires when an `attr[...]: type = code` sits at an address
the layout resolves as data. Four far-call targets do it (`seg_0000:072d`,
`seg_0941:1299`, `seg_0941:1c31`, and `seg_0000:0d98` on its own). Typing the byte
before as `u8` fixes it in isolation but not once the other seeds are present.

They are real routines, so they are listed in `ishar.chani`'s footer and in
`tools/symbols.py`'s dropped-seed report rather than being quietly skipped — a seed that
vanishes without a word is a routine nobody thinks to look for again. Read them with
Spice86's `read_disassembly`.

### A bisect that fails for the wrong reason proves nothing

Hunting the panic above, each candidate database was written to the scratchpad and run
from there. chani resolves `path` relative to the project file, so every one of them
failed on a missing `start-unpacked.exe` — and the script, which only checked the exit
code, reported that all 41 seeds were bad and that the segments alone were bad too.

A probe must distinguish the failure it is looking for from every other failure. The
fixed version greps stderr for `panicked` and aborts outright if it sees `No such file`.

### An import that rewrites its block is not cumulative

`tools/symbols.py` first rebuilt its section from just the run it was given, so
importing a gameplay run *deleted* the seeds imported from the earlier language-menu
run. Coverage went 23.8% → 24.1% while `seg_13d7` quietly fell from 432 decoded
instructions to 13, and the headline number still moved up.

It now merges with what is already there. When a number improves and a component of it
collapses, the number is not the thing to trust.

### Emulators pile up unless something reaps them

`ish start` stopped only the instance recorded in `.ish/state.json`, so anything
started another way -- `run.sh`, a crashed session, an earlier `start` whose state file
was then overwritten -- kept running. Eleven live emulators were found at once, each
holding a port and a CPU.

`ish stop` now kills every Ishar emulator it can find, and `start` reaps before
launching. When something feels slow, count the emulators before blaming the game.

### `list_functions` needs an explicit limit

Called with `{}` it returns `An error occurred invoking 'list_functions'`, which reads
like the tool is broken. Pass `{"limit": 5000}`. It also defaults to 100 -- small enough
to look like a complete answer.

### A blocking tracer and a key-sending timer cannot share one loop

The GDB route is fast because the client blocks on the socket until the stub pushes a
stop. Anything that also needs to act on a timer -- sending keys, taking screenshots --
has to interrupt that block, and every interruption costs a `c`, which is itself a
pause/resume. Measured on the same startup that takes 3.5s untouched:

| loop | time to the first asset |
|---|---|
| blocking, no keys | 3.5s |
| wake every 2s to nudge | 27s |
| wake every 0.4s | 61s |

Faster polling made it worse, which is the giveaway. Keys belong in a separate process
(`tools/nudge.py`): each keypress pauses the machine once, the tracer sees that pause
and continues it, and the tracer never wakes on a timer of its own.

### GDB Z-packet conditions are ignored; MCP conditions are not

Spice86's GDB stub parses `Z0,addr,1;X:ah==0x3d`, answers `OK`, and then breaks on
every hit anyway -- measured spaced, unspaced, single-term and with `||`, all
unfiltered, stopping on all ~500k INT 21h calls. The same condition through MCP's
`add_breakpoint` filters correctly.

So the fast tracer is a hybrid: **arm the conditional breakpoint over MCP, wait for the
stop over GDB.** The stub notifies its client on *any* pause, not only its own
breakpoints, which is what makes that work. Measured on the same milestone (the boot's
open of `logo.IO`): MCP polling ~420s, hybrid 7.7s.

### Any pause reaches the GDB client, so a stop is not evidence of a breakpoint

An MCP call, a screenshot, the UI -- each pauses the emulator, and the stub pushes a
stop packet for it. Registers read at such a stop describe wherever the machine
happened to be, which is where a trace full of phantom `op 0x11` entries came from.
Check `ip` against the breakpoint address before believing a stop.

The same trap in the polling tracer: `read_cpu_state` pauses the machine, so catching
`CS:IP` at a hot address proves nothing. Require the stop to still be there with the
cycle count unmoved.

### RSP replies and pushed stops share one stream

The `OK` acking a continue and the stop packet that follows can arrive in either order,
so a register read comes back as `'OK'`. Reads now skip acks and queue stops instead of
returning them as data.

### Exploratory runs should be capped at the answer, not at the budget

Two traces were left to run out 240s and 300s budgets after the first 20 seconds had
already shown the pattern, and eight emulator restarts (~40s each) were spent on
experiments that could have shared one instance. That, not the emulation, is where 27
minutes went.

Cap exploratory runs at ~30s, reuse a running emulator, and stop at the first decisive
signal.

## Unsupervised sessions

`/goal` runs until the objective is met. `ROADMAP.md` holds the tasks and their
**Done when** lines — a goal names one, and that line is the definition of finished, not
the prose of the goal. The `goal` skill carries the rules; two matter more than the rest:

**Check every premise before acting on it.** A brief repeats an earlier note with more
confidence than it was written with. If the finding it cites has an **Evidence:** line
naming a byte-for-byte comparison or a live breakpoint, it holds; if it cites a name or
a guess, verify it cheaply first.

**Stopping is a result.** Acceptance met, premise dead, three failed attempts at the
same approach, a decision that is the user's, or the crash budget spent — stop and
report. A goal whose premise died is finished, not a licence to improvise a new one.

## Tools

| | |
|---|---|
| `tools/unpack.py` | rebuild `start-unpacked.exe` from the shipped binary |
| `tools/verify-unpack.py` | prove it byte for byte against the emulator — the gate |
| `tools/segmap.py` | derive the segment map and far-call seeds from the relocation table |
| `tools/symbols.py` | import the functions Spice86 executed as chani code seeds |
| `tools/disasm.sh` | regenerate `ishar-listing.txt` and print coverage |
| `tools/cover.py` | coverage only; refuses a listing older than the database |
| `tools/addr.py` | runtime `CS:IP` ↔ listing `seg_xxxx:offset` |
| `tools/ish` | the measurement harness: start/boot/status/regs/mem/dis/bp/keys/shot/wait |
| `tools/rsp.py` | minimal GDB remote-protocol client for Spice86's stub |
| `tools/gdbtrace.py` | DOS file-call tracer: MCP arms the breakpoint, GDB delivers stops |
| `tools/png.py` | PNG read/write with no third-party imaging library |

chani itself stays external and unvendored (`CHANI_HOME`): it carries no licence, so it
is a local instrument like a debugger, never a build dependency.

## Driving the game

`run.sh` runs the **unpacked** binary by default, regenerating
`ishar_legend_of_the_fortress_DOSGamer.com/start-unpacked.exe` when it is missing or
older than the shipped `start.exe`. It sits beside the game's own files because
`--CDrive` makes that folder `C:`, and it is derived, so it is gitignored. Attaching a
debugger to the shipped binary shows you the unpacker, not the game;
`EXE=.../start.exe ./run.sh` when that is what you want.

The unpacked image loads at the same `017d`, so listing addresses map one to one either
way — checked by booting it through to gameplay.

`run.sh` is for playing it. Measurement wants determinism — fixed clock, sync
rendering, dummy audio — which is what `tools/ish` will be. Until it exists, drive it
over the MCP port `run.sh` prints at startup.

Boot sequence, roughly 40 s to the language menu: `1` (top row works only after
`remap-digits.sh`, which `run.sh` applies automatically), Escape past the credits, then
Escape/Space through the intro. The intro loops back to the language menu if left
alone.

The game dies in the timer interrupt after a couple of minutes — see `FINDINGS.md`
§5.1. Sessions are short until that is fixed; plan measurements accordingly and check
the log for `Emulation failed` before trusting a reading taken near the end of a run.
