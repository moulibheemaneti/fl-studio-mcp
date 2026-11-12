# name=FLMCP SysEx Spike
"""Phase 0 spike: can our program and FL talk over MIDI SysEx?

Set up in FL (Options > MIDI Settings):
  Input  "IAC Driver FLMCP-REQ": enable, Controller type = FLMCP SysEx Spike, Port 10
  Output "IAC Driver FLMCP-RES": enable, Port 10 (the same number links it to this script)

Message format, both directions:
  F0 7D 46 4D <kind> <ASCII JSON> F7
  7D is MIDI's manufacturer ID for non-commercial use, 46 4D is "FM" (our tag),
  kind 01 = request (Mac -> FL), 02 = response (FL -> Mac). Anything else is ignored.
  ASCII JSON keeps every byte below 0x80, which SysEx requires.

The Mac side is scripts/sysex_spike.py. Imports only json, time and FL modules
(see DECISIONS.md). Read-only: it never changes the project.

Throwaway: delete once DECISIONS.md records the result.
"""

import json
import time

import device
import general
import mixer
import transport

HEADER = bytes([0x7D, 0x46, 0x4D])
KIND_REQUEST = 0x01
KIND_RESPONSE = 0x02


def OnInit():
    print(
        f"FLMCP SysEx spike: input port {device.getPortNumber()}, "
        f"output linked: {device.isAssigned()}"
    )


def OnSysEx(event):
    raw = bytes(event.sysex)
    data = raw[1:] if raw[:1] == b"\xf0" else raw
    data = data[:-1] if data[-1:] == b"\xf7" else data
    if len(data) < 4 or data[:3] != HEADER or data[3] != KIND_REQUEST:
        return
    event.handled = True

    started = time.perf_counter()
    request_id = command = None
    try:
        request = json.loads(data[4:].decode("ascii"))
        request_id = request.get("id")
        command = request.get("command")
        result = handle(command, request.get("args", {}), len(raw))
        reply = {"id": request_id, "ok": True, "result": result}
    except Exception as exc:
        reply = {"id": request_id, "ok": False, "error": repr(exc)}
    reply["fl_ms"] = round((time.perf_counter() - started) * 1000, 3)

    try:
        sent = send(reply)
        print(f"FLMCP SysEx spike: {command} {request_id}: in {len(raw)} B, out {sent} B")
    except Exception as exc:
        print(f"FLMCP SysEx spike: {command} {request_id}: reply failed {exc!r}")


def handle(command, args, raw_len):
    if command == "ping":
        return {
            "api_version": general.getVersion(),
            "tempo": mixer.getCurrentTempo(),
            "playing": bool(transport.isPlaying()),
            "ppq": general.getRecPPQ(),
            "port": device.getPortNumber(),
        }
    if command == "echo":
        return {
            "pad_len": len(args.get("pad", "")),
            "raw_len": raw_len,
            "pad": "x" * int(args.get("reply_bytes", 0)),
        }
    raise ValueError(f"unknown command: {command}")


def send(reply):
    body = json.dumps(reply, ensure_ascii=True, separators=(",", ":")).encode("ascii")
    frame = b"\xf0" + HEADER + bytes([KIND_RESPONSE]) + body + b"\xf7"
    device.midiOutSysex(frame)
    return len(frame)
