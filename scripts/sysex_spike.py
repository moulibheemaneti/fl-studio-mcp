"""Phase 0 SysEx spike: send JSON to FL and back over the two IAC buses.

    uv run scripts/sysex_spike.py             # self-test, then ping, latency and sizes with FL
    uv run scripts/sysex_spike.py --selftest  # Mac-only check, FL not needed

Needs the IAC ports FLMCP-REQ and FLMCP-RES, and FL running the
"FLMCP SysEx Spike" controller script (fl_scripts/spike/device_FLMCPSysexSpike.py).

Message format, both directions:
    F0 7D 46 4D <kind> <ASCII JSON> F7
7D is MIDI's manufacturer ID for non-commercial use, 46 4D is "FM" (our tag).
kind 00 = self-test, 01 = request (Mac -> FL), 02 = response (FL -> Mac).
ASCII JSON keeps every byte below 0x80, which SysEx requires.

Throwaway: the real version will live in src/fl_mcp/bridge/.
"""

import argparse
import json
import queue
import statistics
import sys
import time
import uuid
from dataclasses import dataclass

import mido

REQUEST_PORT = "IAC Driver FLMCP-REQ"  # Mac -> FL
RESPONSE_PORT = "IAC Driver FLMCP-RES"  # FL -> Mac
HEADER = bytes([0x7D, 0x46, 0x4D])
KIND_SELFTEST, KIND_REQUEST, KIND_RESPONSE = 0x00, 0x01, 0x02
SIZES = (64, 256, 1024, 4096, 8192, 16384)
LATENCY_PINGS = 20

NO_REPLY_HELP = """\
No reply from FL within {timeout:g} s. In FL, Options > MIDI Settings:
  Input  "IAC Driver FLMCP-REQ": enabled, Controller type "FLMCP SysEx Spike", Port 10
  Output "IAC Driver FLMCP-RES": enabled, Port 10
View > Script output should say "FLMCP SysEx spike: input port 10, output linked: True"."""


def encode(kind: int, payload: dict) -> mido.Message:
    body = json.dumps(payload, ensure_ascii=True, separators=(",", ":")).encode("ascii")
    return mido.Message("sysex", data=HEADER + bytes([kind]) + body)


def frame_size(message: mido.Message) -> int:
    return len(message.data) + 2  # mido leaves out F0 and F7


class Inbox:
    """Collects our SysEx messages arriving on one input port."""

    def __init__(self, port_name: str) -> None:
        self._queue: queue.Queue = queue.Queue()
        self._port = mido.open_input(port_name, callback=self._on_message)

    def _on_message(self, message: mido.Message) -> None:
        data = bytes(message.data) if message.type == "sysex" else b""
        if len(data) < 4 or data[:3] != HEADER:
            return
        try:
            payload = json.loads(data[4:].decode("ascii"))
        except ValueError:
            return
        self._queue.put((time.perf_counter(), data[3], payload, frame_size(message)))

    def wait(self, kind: int, message_id: str, timeout: float) -> tuple[float, dict, int]:
        deadline = time.perf_counter() + timeout
        while (remaining := deadline - time.perf_counter()) > 0:
            try:
                arrived, got_kind, payload, size = self._queue.get(timeout=remaining)
            except queue.Empty:
                break
            if got_kind == kind and payload.get("id") == message_id:
                return arrived, payload, size
        raise TimeoutError(f"no reply to {message_id} within {timeout:g} s")

    def close(self) -> None:
        self._port.close()


@dataclass
class Result:
    reply: dict
    rtt_ms: float
    sent_bytes: int
    received_bytes: int


class FLLink:
    """Requests go out on FLMCP-REQ; FL's replies come back on FLMCP-RES."""

    def __enter__(self) -> "FLLink":
        self._out = mido.open_output(REQUEST_PORT)
        try:
            self._inbox = Inbox(RESPONSE_PORT)
        except Exception:
            self._out.close()
            raise
        return self

    def __exit__(self, *exc_info: object) -> None:
        self._inbox.close()
        self._out.close()

    def request(self, command: str, args: dict | None = None, timeout: float = 3.0) -> Result:
        message_id = uuid.uuid4().hex[:8]
        message = encode(KIND_REQUEST, {"id": message_id, "command": command, "args": args or {}})
        started = time.perf_counter()
        self._out.send(message)
        arrived, reply, received = self._inbox.wait(KIND_RESPONSE, message_id, timeout)
        return Result(reply, (arrived - started) * 1000, frame_size(message), received)


def row(direction: str, size: int, frame: int, rtt: float | None, status: str) -> None:
    rtt_text = f"{rtt:8.1f} ms" if rtt is not None else "        --"
    print(f"  {direction:<9} {size:>6} B pad  {frame:>6} B frame  {rtt_text}  {status}")


def selftest() -> bool:
    """Mac only: send on FLMCP-REQ and listen on it too (IAC echoes to every listener)."""
    print("Self-test, Mac only (send and receive on FLMCP-REQ):")
    ok = True
    with mido.open_output(REQUEST_PORT) as out:
        inbox = Inbox(REQUEST_PORT)
        try:
            for size in SIZES:
                message_id = uuid.uuid4().hex[:8]
                message = encode(KIND_SELFTEST, {"id": message_id, "pad": "x" * size})
                started = time.perf_counter()
                out.send(message)
                try:
                    arrived, payload, _ = inbox.wait(KIND_SELFTEST, message_id, 3.0)
                except TimeoutError:
                    row("loopback", size, frame_size(message), None, "FAIL (timeout)")
                    ok = False
                    continue
                intact = len(payload["pad"]) == size
                ok &= intact
                status = "OK" if intact else "FAIL (damaged)"
                row("loopback", size, frame_size(message), (arrived - started) * 1000, status)
        finally:
            inbox.close()
    return ok


def sweep(link: FLLink, direction: str, to_fl: bool) -> bool:
    """Grow one direction's message size until something breaks."""
    for size in SIZES:
        args = {"pad": "x" * size, "reply_bytes": 0} if to_fl else {"reply_bytes": size}
        try:
            result = link.request("echo", args)
        except TimeoutError:
            row(direction, size, 0, None, "FAIL (no reply, stopping this direction)")
            return False
        reply = result.reply
        if not reply.get("ok"):
            row(direction, size, 0, result.rtt_ms, f"FAIL (FL error: {reply.get('error')})")
            return False
        got = reply["result"]["pad_len"] if to_fl else len(reply["result"]["pad"])
        frame = result.sent_bytes if to_fl else result.received_bytes
        status = "OK" if got == size else f"FAIL (got {got} of {size})"
        row(direction, size, frame, result.rtt_ms, status)
        if got != size:
            return False
    return True


def test_fl() -> bool:
    print("\nWith FL (requests on FLMCP-REQ, replies on FLMCP-RES):")
    with FLLink() as link:
        try:
            ping = link.request("ping")
        except TimeoutError:
            print(NO_REPLY_HELP.format(timeout=3.0))
            return False
        print(f"  ping: {ping.rtt_ms:.1f} ms, FL says {ping.reply['result']}")

        rtts = [link.request("ping").rtt_ms for _ in range(LATENCY_PINGS)]
        print(
            f"  latency over {LATENCY_PINGS} pings: min {min(rtts):.1f} ms, "
            f"median {statistics.median(rtts):.1f} ms, max {max(rtts):.1f} ms"
        )
        print("  sizes:")
        to_fl_ok = sweep(link, "Mac -> FL", to_fl=True)
        from_fl_ok = sweep(link, "FL -> Mac", to_fl=False)
    return to_fl_ok and from_fl_ok


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--selftest", action="store_true", help="Mac-only check, skip FL")
    args = parser.parse_args()
    try:
        ok = selftest()
        if not args.selftest:
            ok = test_fl() and ok
    except TimeoutError as exc:  # must come first: TimeoutError is a subclass of OSError
        print(f"FL stopped answering mid-test ({exc}).")
        return 1
    except OSError as exc:
        print(f"Could not open a MIDI port ({exc}). Are FLMCP-REQ and FLMCP-RES online?")
        return 1
    print("\nAll SysEx checks pass." if ok else "\nSome SysEx checks failed.")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
