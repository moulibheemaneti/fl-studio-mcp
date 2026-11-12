# Why the file mailbox doesn't work

> **Phase 0 finding, 12 Nov 2026.** Tested on FL Studio 2026 (26.1), MIDI scripting API 45, FL's built-in Python 3.12.1, macOS (Apple Silicon).

## Summary

- The plan's **file mailbox** assumed that Python scripts inside FL can read and write JSON files in `~/.fl-mcp/`. **They can't.** FL runs scripts behind a sandbox that blocks most file operations.
- **Controller (device) scripts** can read files **only in their own folder**, and **can't write files anywhere**.
- So FL can never send a reply through a file. Replies have to travel as **MIDI SysEx** messages, which FL documents and allows.
- **Piano roll scripts** can read and write files **only inside `Settings/Piano roll scripts/`** (including a subfolder). Renaming, deleting and making folders are blocked there too (§3.5).
- **SysEx works** in both directions: about 0.2 ms per round trip, and a single 16 KB message got through each way (§3.6).

---

## 1. What the original plan assumed

```
Claude → MCP server ──writes request.json──► ~/.fl-mcp/ (mailbox)
                    ──MIDI "doorbell"──► IAC Driver ──► device script (inside FL)
                                                          │ reads request.json    ← assumption A
                                                          │ calls the FL API
                                                          └ writes response.json  ← assumption B
MCP server ──writes notes.json──► ~/.fl-mcp/ ──► piano roll script reads it      ← assumption C
```

| Assumption | Result |
|---|---|
| The MCP server can write to `~/.fl-mcp/` | ✅ True. It's a normal Mac program |
| MIDI over the IAC Driver reaches FL | ✅ True |
| **A.** A device script can read `~/.fl-mcp/request.json` | ❌ **False.** Blocked |
| **B.** A device script can write `~/.fl-mcp/response.json` | ❌ **False.** Blocked, and writing is blocked in every folder tested |
| **C.** A piano roll script can read `~/.fl-mcp/notes.json` | ❌ **False** in `~/.fl-mcp`. ✅ But reading and writing work inside `Settings/Piano roll scripts/` (§3.5) |

---

## 2. Why FL blocks file access

**FL uses its own Python, not the Mac's.** FL ships Python 3.12 inside the app, at `FL Studio 2026.app/Contents/Resources/FL/Shared/Python/`, and runs every script in it.

**FL attaches a guard to that Python.** Python has a built-in checkpoint called an **audit hook**. Before a risky action such as opening, renaming or deleting a file, or making a folder, Python asks the hook for permission. FL's engine (`Contents/Libs/FLEngine_x64.dylib`) calls `PySys_AddAuditHook`, and its hook refuses most file operations.

**How to recognise a refusal.** When the hook says no, Python reports a confusing internal error instead of a normal one:

| Error you see | Meaning |
|---|---|
| `SystemError: <...> returned NULL without setting an exception` | FL's hook refused the action |
| `TypeError: bad argument type for built-in operation` | FL's hook refused a low-level `os.open()` call |
| `FileNotFoundError` / `PermissionError` | A normal error. **Not** what we see, so the cause is neither a missing file nor macOS permissions |

**It isn't macOS.** `~/.fl-mcp` is an ordinary folder that macOS doesn't protect, and our own program reads and writes it with no problems. Only Python **inside FL** is restricted.

**It isn't documented.** Neither the [MIDI scripting manual](https://www.image-line.com/fl-studio-learning/fl-studio-online-manual/html/midi_scripting.htm) nor the [piano roll scripting manual](https://www.image-line.com/fl-studio-learning/fl-studio-online-manual/html/pianoroll_scripting_api.htm) mentions any file restriction. The rules could change in any FL update without notice. The most likely reason for the sandbox is security: scripts are often downloaded from forums, and the guard stops a downloaded script from reading or deleting your files.

---

## 3. Evidence

### 3.1 Spike runs

The spike scripts live in [`fl_scripts/spike/`](../fl_scripts/spike/). Run them with [`scripts/check_phase0.py`](../scripts/check_phase0.py).

| Run | What happened | What it showed |
|---|---|---|
| 1 | All imports worked (`json`, `os`, `time`, `uuid`, `datetime`, `pathlib`, `tempfile`). Then `os.makedirs("~/.fl-mcp")` failed with `SystemError` | The first sign of the guard |
| 2 | **Reload script** crashed FL three times. The next run failed inside `tempfile.gettempdir()` with `TypeError` | Two side issues, see §4. The `tempfile` call was a bug in the spike (an unguarded call), now fixed |
| 3 | Each file action tried on its own. Only listing a folder and checking that it exists worked | **The controller sandbox blocks reading and writing** |

Run 3 results (controller script):

```
mailbox.listdir:      ok
mailbox.read:         SystemError("<class '_io.FileIO'> returned NULL without setting an exception")
mailbox.write:        SystemError("<class '_io.FileIO'> returned NULL without setting an exception")
mailbox.replace:      SystemError('<built-in function replace> returned NULL without setting an exception')
mailbox.remove:       SystemError('<built-in function remove> returned NULL without setting an exception')
fl_user_data.write:   SystemError("<class '_io.FileIO'> returned NULL without setting an exception")
mailbox.mkdir:        SystemError('<built-in function mkdir> returned NULL without setting an exception')
save_report:          SystemError("<class '_io.FileIO'> returned NULL without setting an exception")
```

### 3.2 Checked by hand in FL's Interpreter

These lines were typed into **View → Script output → Interpreter**, with the spike selected as the controller script. No spike code was involved.

| Line typed | Result |
|---|---|
| `open('~/.fl-mcp/spike_input.json').read()` (full path) | ❌ `SystemError (<class '_io.FileIO'> returned NULL without setting an exception)` |
| `open('<Settings>/Hardware/FLMCP Spike/device_FLMCPSpike.py').readline()` | ✅ `'# name=FLMCP Spike\n'` |
| `open('<Settings>/Hardware/FLMCP Spike/probe.txt', 'w').write('hi')` | ❌ Same `SystemError`, and no file was created |

`<Settings>` is `~/Documents/Image-Line/FL Studio/Settings`.

Reads are probably allowed in the script's own folder because a controller script can be split across several `.py` files that import each other. FL's own Novation script does this.

### 3.3 Controller script access on FL 2026

| Action | `~/.fl-mcp/` | FL user folder | Script's own folder |
|---|---|---|---|
| Read a file | ❌ | not tested | ✅ |
| Write a file | ❌ | ❌ | ❌ |
| Rename, delete, make a folder | ❌ | ❌ | not tested |
| List a folder, check it exists | ✅ | not tested | not tested |

### 3.4 Other projects hit the same wall

Read for reference only. No code was copied.

| Project | How it talks to the controller script | Notes |
|---|---|---|
| [rosasynthesiz/flstudio-mcp](https://github.com/rosasynthesiz/flstudio-mcp) | **SysEx both ways** | Its first version used a file queue and dropped it because of the sandbox. Tested on FL 25.2.5 |
| [ae5n/fl-mcp](https://github.com/ae5n/fl-mcp) | **SysEx both ways** (IAC Bus 1 and Bus 2) | Built for FL 2026 on macOS. Reports the same `SystemError`/`TypeError`, and that piano roll scripts may only use files in their own folder |
| [emmggew-svg/fl-mcp-2026](https://github.com/emmggew-svg/fl-mcp-2026) | SysEx | A port of rosasynthesiz to FL 2026 |
| [karl-andres/fl-studio-mcp](https://github.com/karl-andres/fl-studio-mcp) | Files in the script's own `Hardware/` folder | Reading its commands would work (§3.2), but **writing its replies would fail** on FL 2026 |
| [alansork/fl-studio-mcp](https://github.com/alansork/fl-studio-mcp) | Files in `~/.fl-studio-mcp` | Both reading and writing would fail on FL 2026 |

### 3.5 Piano roll script access on FL 2026

This uses the dialog-free [`FLMCP_Spike.pyscript`](../fl_scripts/spike/FLMCP_Spike.pyscript), run from the piano roll via **Tools → Scripts column → FLMCP_Spike**.

| Action | `Piano roll scripts/` | `Piano roll scripts/FLMCP Spike/` (made by the Mac side) | `~/.fl-mcp/` |
|---|---|---|---|
| Read a file | ✅ | ✅ | ❌ |
| Write a file | ✅ | ✅ | ❌ |
| Rename (`os.replace`) | ❌ | ❌ | ❌ |
| Delete | ❌ | ❌ | ❌ |
| Make a folder | ❌ | — | — |

So piano roll scripts are limited to their own folder, as ae5n reported. Because renaming is blocked as well, FL can't use "write a temporary file, then rename it" to make a write safe. ae5n uses a marker file for that reason.

### 3.6 SysEx round trip on FL 2026

| Piece | Setting |
|---|---|
| IAC port `FLMCP-REQ` | Mac → FL. In FL: **Input**, controller type *FLMCP SysEx Spike*, Port 10 |
| IAC port `FLMCP-RES` | FL → Mac. In FL: **Output**, Port 10 (the same number links it to the script) |
| Test | `uv run scripts/sysex_spike.py`, run twice from two terminals with matching results |

| Test | Result |
|---|---|
| Ping | ✅ FL answered with API 45, PPQ 96, port 10 |
| Latency over 20 pings | ✅ Median 0.1–0.2 ms, max about 1 ms |
| Mac → FL, single messages from 64 B to 16 KB | ✅ All arrived intact (16 KB in about 1 ms) |
| FL → Mac, single messages from 64 B to 16 KB | ✅ All arrived intact (16 KB in about 3.6 ms) |
| FL hearing its own replies | ✅ It doesn't. FL only replies on `FLMCP-RES` |

---

## 4. Other findings that affect FL-side code

| Finding | Evidence | Rule for our FL scripts |
|---|---|---|
| Importing `datetime` crashes FL on **Reload script** | 3 crash reports (`~/Library/Logs/DiagnosticReports/OsxFL-*.ips`). All abort inside `_datetime` setup. Reload starts a fresh Python environment, and Python 3.12's `datetime` can't be set up twice | Import only `json`, `os`, `time` |
| `tempfile` fails | It uses low-level `os.open()`, which the guard rejects with `TypeError` | Never use `tempfile` or `os.open` |
| Making folders fails | `os.mkdir` is blocked | The Mac side creates every folder |
| Piano roll scripts with `createDialog()` + `apply()` turn on **live preview**: `apply()` runs again whenever a dialog control changes | FL's local `Piano roll script reference.txt` and the manual | The notes script has **no dialog**: plain top-level code runs once per click |
| `Utils.ShowMessage` "should not be called from within the apply() call" | Piano roll manual | No popups in the notes script. Popups also block keyboard-shortcut triggering |
| Renaming and deleting are blocked in piano roll scripts too | §3.5 | Files FL writes are committed with a marker file: write the body, then a small "done" file. The Mac side does any renaming and cleanup |
| `mixer.getCurrentTempo()` returns BPM × 1000 (140 BPM → `140000`), although the stubs say it returns BPM | SysEx ping | Divide by 1000 |

---

## 5. What still works

| Capability | Status | Source |
|---|---|---|
| The MCP server reading and writing any folder, including FL's script folders | ✅ | A normal Mac process |
| MIDI from the server to FL over the IAC Driver | ✅ | Tested in Phase 0 |
| **SysEx into a controller script** (`OnSysEx`) | ✅ Documented and **tested** (§3.6) | MIDI scripting manual |
| **SysEx out of a controller script** (`device.midiOutSysex`), sent to the output whose **Port number matches** the script's input | ✅ Documented and **tested** (§3.6) | MIDI scripting manual |
| A piano roll script reading and writing files in `Settings/Piano roll scripts/` | ✅ Works (§3.5), but **undocumented** | Spike |
| "Run last script again" (**Cmd+Opt+Y**) | ✅ A built-in menu item: piano roll **Tools → Scripts** column | FL 2026 menu |
| Writing drum steps into the Channel rack sequencer from a controller script (`channels.setGridBit`) | ✅ Documented | MIDI scripting manual |
| A controller script reading files in its own folder | ✅ Works, but **undocumented** | §3.2 |

---

## 6. What this means for the design

Only `bridge/` changes. The layering rule in the README was made for exactly this, and `theory/` and `tools/` don't change.

**Commands (decision pending):**

| | A: SysEx both ways | B: File in, SysEx out |
|---|---|---|
| Mechanisms to build and debug | One | Two |
| SysEx encoding and chunking | Needed | Still needed, for replies |
| Second IAC bus | Needed | Needed |
| Depends on undocumented behaviour | No | Yes (reading the script's own folder) |

**Recommendation: A.** B still needs all of A's SysEx work for the replies. Its only advantage is large requests, but commands are small. The large payloads (notes) go through the piano roll. The SysEx spike (§3.6) backs this up: it works, it takes well under a millisecond, and 16 KB fits in one message.

**Notes:** piano roll scripts can read and write in their own folder (§3.5), so `notes.json` moves to `Settings/Piano roll scripts/FLMCP/`.
- The Mac side writes it safely, as a temporary file that it then renames, because a normal Mac process is allowed to rename.
- FL replies with a body file followed by a marker file, because FL can't rename.
- Adding notes still takes one click. Later, Cmd+Opt+Y can trigger it automatically.

**Roadmap:** Phases 2–4 in the README need rewriting once the commands decision is confirmed.

---

## 7. Open questions

- [x] Can a **piano roll** script read and write in `Settings/Piano roll scripts/`? **Yes**, but it can't rename or delete (§3.5).
- [x] Does SysEx work in both directions, and how large can a message be? **Yes.** 16 KB per message works each way; larger sizes are untested. The possible SysEx freeze another project mentions for FL 26.1.7 didn't show up.
- [ ] Does **Reload script** stay stable once `datetime` is no longer imported?
- [ ] Can our program trigger **Cmd+Opt+Y** ("Run last script again", a built-in menu item) to remove the manual click after one run per session? This needs macOS Accessibility permission.

## 8. How to reproduce

1. Install and check:

   ```bash
   uv run scripts/check_phase0.py --install
   ```

2. **Controller file access:** set an IAC input's **Controller type** to *FLMCP Spike* (Options → MIDI Settings), then restart FL. The results appear in **View → Script output**. Or test by hand in the **Interpreter** tab with the lines from §3.2.
3. **SysEx:** set up the ports as in §3.6 with controller type *FLMCP SysEx Spike*, then run:

   ```bash
   uv run scripts/sysex_spike.py
   ```

4. **Piano roll file access:** open a piano roll, then choose **Tools → Scripts column → FLMCP_Spike**.
5. Check everything:

   ```bash
   uv run scripts/check_phase0.py
   ```
