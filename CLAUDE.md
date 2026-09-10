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
screenshots a while apart? known timing for this phase?

**And the mirror of it: a still screen is not a slow screen either.** The sentence that
used to end this scar -- "Ishar's intro is minutes long and mostly dark" -- was wrong,
and it was then read back out of this file and offered to the user as the explanation
for a frozen frame. The intro is about three screens. What was actually happening was a
fault: `#UD ... modrm mod=3` at `017D:194D`, sitting in the log the whole time.

So the check is not "which story explains the still screen" -- it is **`tools/ish
status` first, story never**. The log answers it in a second and cannot be talked into
an answer. `tools/gdbtrace.py` now reads that log every 2s and aborts with `EMULATOR
FAULTED` rather than running out its budget against a dead machine, because a rule that
depends on remembering to look is a rule that gets walked past (see the top of this
file).

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

### Search for the value as stored, not as captured

`logo.io` was recorded as carrying no palette because a search for the captured DAC
bytes found nothing in the file. The DAC holds 6-bit values; the file stores 8-bit ones
and the game shifts them right by two on the way out. The bytes were there the whole
time, in the obvious place, in the obvious format.

Before concluding something is absent, ask what transformation sits between the copy you
have and the copy you are looking for -- scaling, packing, endianness, a shift -- and
search for the pre-image too. A negative result from one encoding is not a negative
result.

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

### A wrong width and a broken decoder look identical

`tools/ioscan.py` guessed sprite offsets by scanning for plausible 8-byte headers.
It found `logo.io`'s two known sprites, which read as success; run over all 108
files it produced 76 images of which exactly one was a picture. The rest was noise,
and the obvious next thought was that the decoder is wrong for files other than
`logo.io`.

It is not. `logo.io` decodes byte-for-byte correctly against the emulator's
framebuffer, and rendering *it* as a raw 320-wide dump looks just as much like
noise as the others. Any 8bpp image laid out at the wrong width does.

So: before blaming a decoder for ugly output, render a **known-good** file the same
wrong way. If it looks equally bad, the decoder is not the problem and the layout is.
And a heuristic that reproduces the one case you already knew has not been tested —
`ioscan.py` is kept as a lead-generator, never as a source of truth.

### A routine that fires is not a routine that fires *when you care*

`seg_0e97:038b` was established as "the sprite blitter" by breaking on it and watching
it run 445 times. It does -- during the launcher, the title screen and the intro. In
the game viewport it fires **zero times in 30 seconds** of walking around, so
everything measured through it describes the intro's renderer, not the game's.

The check that costs nothing: after confirming a breakpoint fires, confirm it fires in
the *phase the question is about*. Count hits with the game in the state you actually
care about before building on the numbers.

The framebuffer is the cheap oracle for this kind of doubt: reading 0xA0000 over GDB and
rendering it with the captured DAC reproduces the screen exactly, so "is my instrument
lying?" can always be settled in one command before blaming the data
(`captures/t11m2-vram.png`).

### A listing segment is not a runtime segment

`tools/ish dis 0e97:038b` passed `0x0e97` to Spice86 as a segment register value, so it
disassembled bytes 0xe97 paragraphs from address zero instead of from the program. It
printed plausible-looking rubbish -- `aas`, `ret 0e2f7h` -- while `ishar-listing.txt` had
the correct instructions all along, and the disagreement was read as the *listing* being
wrong. That cost a wrong turn in T11k.

A listing segment name is an **image paragraph**; the runtime segment is `load + seg`.
When a tool and the listing disagree about the same address, dump the bytes from the
image as a third opinion before believing either.

### A trace taken mid-game cannot see what startup did

Ishar was recorded as not using the mouse because a breakpoint on the INT 33h handler
caught zero calls in 20 seconds of play. It uses the mouse: it installs an *event
handler* during startup (`AX=0x0c`) and never calls INT 33h again. The trace was right
and the conclusion was wrong.

Before concluding a program does not use a facility, trace it **from a cold boot**.
Anything configured once at startup -- interrupt handlers, palettes, modes, device setup
-- is invisible to a trace that begins later, and the absence looks exactly like a
feature that was never there.

### A superseded finding stays in the roadmap until it is rewritten

`T11m`'s entry stated `group = word0 >> 8` for two sessions after `T11r` disproved it and
after `FORMATS.md` had been corrected. Ticking a status is not the same as fixing the
prose, and the prose is what the next reader believes -- especially the reader who greps
the roadmap rather than the spec.

When a finding is overturned, grep both `ROADMAP.md` and `FORMATS.md` for the old claim in
the same step as recording the new one. And say in the entry that the old version was
believed: a task that reads as if it were always right teaches nothing about how it went
wrong.

### A property proved for one asset is not a property of the format

Index 0 was established as transparent from `logo.io`'s sprite -- 4,117 pixels decoded as
0 against the framebuffer's background, a genuinely byte-for-byte result (FORMATS 3.7).
It was then applied to every sprite in the game. That sprite is **mode 0x14**, the single
mode whose handler tests for zero; 4bpp sprites are opaque and write colour 0 like any
other. Every 4bpp asset was rendered with holes punched through it for weeks, which looks
like scattered green speckle and reads as a palette fault, not a transparency fault.

The check: when a fact is measured on one asset, look at how many the measurement covers
before generalising. Here the mode byte was already decoded and said five formats existed
(3.10) -- the evidence that the rule was narrower than the claim was in the same file.

### Never downsample a dithered image to look at it

`presti.io` was reported as having wrong colours twice while the extraction was correct
both times: the review sheet scaled 144x35 sprites down by two to fit a cell, and sampling
a 4bpp dithered image at every second pixel turns it into coloured speckle.

Review sheets are 1:1 or they are lying. Open the actual PNG at full size before chasing a
colour bug, and if a sheet must scale, upscale by whole pixels -- never sample down.

### When output looks wrong, suspect the viewer before the data

Both of the above presented identically: "the colours are wrong". One was a rendering rule
applied too widely, one was the contact sheet's scaler, and neither was the palette that
got investigated first. Before re-deriving a format, render one known-good asset through
the same path -- `logo.io` has a framebuffer-verified reference for exactly this.

### A blocker is a claim with an expiry date

Three tasks sat blocked on conditions that had stopped being true. `T07` on "nudging over
MCP pauses the emulator", written before `tools/nudge.py` moved key-sending to a separate
process -- the documented fix for that exact problem, used by every probe since. `T10` on a
breakpoint that "never fired", which is the signature of the IP bug in T27b -- though there
it turned out to be a *dead premise* instead: `main.io` takes the LZ path, so a breakpoint
on the RLE decoder could never have fired, and the task was never updated when the mode
branch was found. `T11g3` on an emulator that had stalled at 1% CPU, which is not a
property of the task at all.

Two rules:

- **When a tool bug is fixed, sweep the roadmap for tasks whose blocker was that class of
  failure.** After T27b I rechecked one task -- T29d -- and left the others. A blocker
  written in the past tense is evidence about a past run, not about the task.
- **When a finding changes what a task rests on, edit the task in the same step.** T10's
  remaining clause was impossible from the moment the mode branch was discovered, and it
  survived because nobody went back.

Grepping `ROADMAP.md` for "never fired", "did not fire", "0 hits", "stalled" and the like
takes seconds and found all three.

### Proposing work in the reply is not filing it

The `main.io` disassembler was offered as "the obvious next step" in three separate
replies and never written into `ROADMAP.md`. The user eventually asked whether it was on
the roadmap; it was not. Everything that made it look obvious -- T27 proving main.io is
the running script, the four dispatch tables, the decoded 0x45 handler -- was recorded,
and the task those facts pointed at was not.

The rule already in this file says future work goes in the roadmap rather than the chat.
The failure mode it misses is *this* one: proposing something so often it feels filed.
**Write the entry in the same step as the recommendation**, not after the user agrees.

### A regex that edits the database can eat the database

Replacing one annotation with
`re.sub(r'^attr\[seg_0000:3a84\]:.*?\n\]\]\]\n', new, text, flags=re.S|re.M)`
looks surgical and is not: with `re.DOTALL`, `.*?` runs from that annotation to the
**next** `]]]` anywhere in the file. The entry being replaced was a one-liner, so the
match swallowed 149 following annotations and they were committed as deleted.

Nothing complained. `disasm.sh` still ran, the listing still looked right, and the loss
showed up only as coverage sliding 49.6% -> 47.9% two tasks later -- and was nearly
misread as a legitimate correction.

Edit the database **line by line**, never with a multi-line regex, and after any edit
check `grep -c '^attr\[' ishar.chani` against what it was. A count that falls when you
meant to add is the whole check.

### A structural marker still needs corroboration

Palette records turned out to start with `fe ff 00 00`, which looked like the end of the
guessing: a real header, not a heuristic. Searching for it across the game gives **80
hits, of which 17 are palettes** -- the sequence occurs freely inside 4bpp pixel data.
Used on its own it would have given 20 assets a "palette" made of picture bytes, and the
only symptom would have been colours that look wrong, which is exactly the symptom the
marker was introduced to fix.

Two independent signals agreeing is the check: the marker *and* the white/black group
signature. When a structural discovery replaces a heuristic, run both over the whole
corpus and count the disagreements before deleting the heuristic.

### Two weak signals pointing the same way are still weak

The palette group was read out of word 0 because its low byte is constant at 16 and its
high byte spans exactly 0..15 -- the range a group index would have. Both signals were
real and both were consistent with the model, and the model was wrong: the group is in
word 3. Word 0's high nibble is a flag, and 0..15 is simply what four bits do.

"The values are in the right range" is not evidence about *which field* holds a value.
Look for a field whose values are *unequally* distributed the way the answer should be --
`buste.io` settled it in one look, because 33 portraits carrying word0 = 0x0010 cannot all
be in the same palette group, while their word3 spread across 0x60..0xd0.

And when a model cannot be checked directly, render the alternatives and look. The user
identified the right group by eye from a 16-cell sheet in seconds, after two sessions of
failing to prove it from the machine.

### Spice86's GDB stub reports IP as a LINEAR address

`registers()["ip"]` is not the segment offset. At a breakpoint on `seg_0000:93a6` with
`CS = 017d`, the stub reports `ip = 0xab76` -- the linear address the breakpoint was
armed with, not `0x93a6`.

This produced **silent false negatives that were nearly written up as findings**. A probe
comparing `r["ip"] & 0xffff` against a segment offset never matches, so the run reports
zero hits and reads exactly like "this routine never executes". Five such runs in T27,
plus the conclusion in T29d that Spice86 never invokes the mouse callback, all rested on
it. It also silently corrupts address arithmetic: computing `cs*16 + ip` adds the load
segment a second time and puts every reported site `0x17d0` too high, which is where
T11p's list of framebuffer writers came from.

Two rules:

- Compare `r["ip"]` **unmasked** against the linear address passed to `add_breakpoint`.
  Never mask it, and never add `cs*16` to it.
- **A zero-hit result is a claim about the instrument until proven otherwise.** Before
  reporting that a routine does not execute, arm the same probe on something known to run
  -- `seg_0000:93a6` runs thousands of times a second -- and check it reports hits.

### nudge.py keys do not reach the game; MCP keys do

A trace sent Escape/Space through `tools/nudge.py` every 3 seconds for 180 seconds
and the title screen never moved. `tools/ish boot`, sending the *same three keys*
over MCP `send_keyboard_key`, was in the game in **16 seconds and 3 nudges**. Same
keys, same emulator, opposite outcome -- and the failing side looks exactly like a
game that is hung, or protected, or waiting on something clever.

`--drive` now sends over MCP. When a key appears not to work, send it the other way
before concluding anything about the game: three sessions of "the title screen is
frozen" were this.

### A key pressed before the screen exists is a key thrown away

`--drive english` pressed `Kp1` once at t=3s. The language menu does not appear
until ~85s into a cold boot, after `auteur.IO`. The press landed on the title
screen, was discarded, and the run then sat on the menu for its remaining minute
looking like the selection had failed.

The opposite fix broke it differently: pressing `Kp1` every 3s *from the start*
disrupted the boot so badly that `MAIN.IO` never opened (8 file calls in 190s). The
working shape is late **and** repeated -- start after the phase that precedes the
screen, then keep offering it.

### "It did not crash" is not "it worked"

`tools/t08run.sh` retried a trace until it stopped faulting, and reported success
on a French run that survived its whole 300s budget stuck on the language menu with
8 file opens. The retry loop then exited, satisfied.

An acceptance condition has to name the thing you wanted, not the failure you were
avoiding. It now greps for `plaine.IO`, the first outdoor asset, which cannot
appear unless the game proper is running.

### One A and one B is not an A/B -- again

Audio-on faulted at 46.2s; `--audio none` ran 210s clean and played the intro. That
was written into `FINDINGS.md` as "the crash is the sound driver", with a table.
The very next `--audio none` run faulted at 45.1s. The finding survived about ten
minutes.

`A plausible cause is not a cause` is already in this file, from the CFG-reload
mistake, and describes this exactly. What it was missing is the count: **two runs
are not evidence for a flag, whichever way they fall.** Before a flag goes into a
findings file, run it both ways at least twice each -- and if that is too expensive
to do, the honest write-up is "not established", not a table.

### The dispatcher decides, not the routine you landed on

FORMATS 3.13 said "4bpp sprites are opaque", from `expand_4bpp` at `seg_0e97:0ad1`,
which really does write both nibbles with `stosw` and test nothing. The framebuffer
said otherwise, and the reason was four instructions up the call graph:
`sprite_mode_dispatch` at `seg_0e97:0a30` sends mode `0x10` to `0b4c` and mode `0x00`
to `0b40`, and neither reaches `0ad1` at all. Only mode `0x12` does.

This is the same shape as the `tools/io.py` scar -- a real routine, correctly read,
that the inputs you care about never reach. The check that costs nothing: **when a
routine handles one case of a dispatch, read the dispatch**, and write down which
cases arrive. A five-way switch means five answers, and the one you read is at best
a fifth of the rule.

### A sentinel colour is not transparency

`ioscan.py` marked transparent pixels `(0, 255, 0)` because the PNG writer only did
RGB. That is indistinguishable from a sprite that legitimately uses green, and it is
why "green speckle" was read as a palette fault for weeks rather than as the
extractor saying "transparent here".

`tools/png.py` now writes RGBA when handed 4-tuples. When a value means "absent",
give it a channel of its own -- never a magic value inside the data.

### Subtract the phantoms with a control breakpoint

Every attempt to find who writes the framebuffer drowned in stops at `seg_0000:3d64`
(`wait_loop`) and a scatter of singletons, because the keypresses needed to make the
game redraw each pause the machine, and every pause reaches the GDB client.

The fix is a control: arm the same probe, send the same keys, but break on an address
the program never writes -- `0xB8000` is ideal in mode 13h. Whatever shows up there is
the phantom set. Subtract it. In T11p that turned "12 sites, unusable" into two sites
at 16 hits each with zero in the control.

Generally: when an instrument has a known noise source you cannot remove, **measure the
noise under the same conditions and subtract it**, rather than trying to reason about
which hits look plausible.

### A percentage that cannot fall is not a measurement

`tools/vmdis.py main.io --stats` says 97% of the file "decoded as instructions", and
T30's acceptance asked for over 80%. But 219 of the 231 byte values are valid opcodes,
so a linear walk decodes to roughly that from *any* starting offset, aligned or not.
The number would have been just as high on a listing that was wrong end to end.

This is the "coverage is not comprehension" trap wearing a different hat, and it is
worth the same reflex every time a percentage appears: **ask what value it would take
if the thing being measured were completely wrong.** If the answer is "about the same",
it is not evidence. Here the falsifiable version is T38 -- sample the script's own
program counter at the VM fetch and require every sample to land on an instruction
boundary, which a misaligned listing fails immediately.

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
