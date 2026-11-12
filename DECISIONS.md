# Decisions

Short log of non-obvious choices. Newest last. Date + two lines each.

## 2026-11-12 — Python pinned to 3.12 only (`==3.12.*`)
`python-rtmidi` 1.5.8 ships macOS arm64 wheels only up to cp312, so 3.13+ would need a source build.
FL Studio 2026 also embeds Python 3.12 (`Python.framework/Versions/3.12` in the app bundle), so both sides match.

## 2026-11-12 — MCP SDK v2 only (`mcp>=2,<3`, locked at 2.3.0)
`from mcp.server import MCPServer` works; the v1 path `mcp.server.fastmcp` is gone, which confirms v2.
Ignore any tutorial that imports `FastMCP`.

## 2026-11-12 — uv from Homebrew, `uv init --package` src layout
uv 0.13.7 installed with `brew install uv`. The package is `fl_mcp` under `src/`, with an `fl-mcp` entry point.
The entry point is a stub that exits until Phase 1, and it writes to stderr because stdout is the MCP channel.

## 2026-11-12 — Phase 0 spike is two throwaway scripts plus a check script
`fl_scripts/spike/` holds one device script and one piano roll script. Both run the same file checks, because FL's two Python environments might differ.
`scripts/check_phase0.py` writes a nonce into `~/.fl-mcp/`, and each spike must echo it back. That proves FL can read what we write, not just write its own files.

## 2026-11-12 — FL sandboxes script Python with an audit hook
FL's engine calls `PySys_AddAuditHook`, and blocked calls fail with odd errors: `os.mkdir` raised `SystemError(... returned NULL without setting an exception)` and `os.open` (used by `tempfile`) raised `TypeError`.
So the Mac side creates `~/.fl-mcp/` and FL never makes folders. FL-side code uses the built-in `open()` only and catches `Exception`, not just `OSError`.

## 2026-11-12 — FL-side scripts import only `json`, `os`, `time`
Importing `datetime` crashed FL three times on "Reload script" (abort inside `_datetime` init; reports in `~/Library/Logs/DiagnosticReports/OsxFL-*`). Reload starts a fresh interpreter, and 3.12's `datetime` can't be set up twice.
Timestamps in FL code use `time`. The Mac side writes ISO dates in the JSON, and FL never parses them.

## 2026-11-12 — Two IAC buses: `FLMCP-REQ` (Mac → FL) and `FLMCP-RES` (FL → Mac)
An IAC bus delivers every message to every listener, including the sender. With one bus, FL would hear its own replies and could loop forever. With two, each side only hears the other.
In FL, input `FLMCP-REQ` and output `FLMCP-RES` use the same Port number (10), which is how `device.midiOutSysex` finds the output. Request/response names match MCP's JSON-RPC terms.

## 2026-11-12 — Commands travel as SysEx both ways (option A)
Controller scripts can't write files, so replies had to be SysEx anyway. Sending requests as files too would add a second mechanism that relies on undocumented behaviour (reading the script's own folder).
Tested on FL 2026: about 0.2 ms per round trip, and 16 KB in a single message both ways. Details in `docs/file-mailbox-findings.md`. This replaces the file mailbox and MIDI doorbell.

## 2026-11-12 — Notes travel as files in `Settings/Piano roll scripts/FLMCP/`
That folder is the only place piano roll scripts may read and write, and renaming or deleting is blocked even there. `~/.fl-mcp/` is no longer used by FL.
The Mac side writes `notes.json` as a temporary file and renames it. FL writes `result-<id>.json` and then `result-<id>.done` as the commit point, and the Mac side cleans up.

## 2026-11-12 — The notes script has no dialog
Without `createDialog()`/`apply()`, FL runs a piano roll script once per click. With them, `apply()` reruns for live preview and can repeat side effects. A dialog would also block the Cmd+Opt+Y trigger later.

## 2026-11-12 — Tempo from FL is BPM × 1000
`mixer.getCurrentTempo()` returned `140000` for 140 BPM, although the stubs say it returns BPM. The controller script converts it, so the JSON contract always uses plain BPM.
