"""Phase 0 setup check.

    uv run scripts/check_phase0.py            # check everything
    uv run scripts/check_phase0.py --install  # also copy the spike scripts into FL

Checks the Python and package versions, the two IAC buses, one SysEx round trip
with FL, and the piano roll spike's file-access report. Exits 0 only when every
check passes. For SysEx latency and message sizes, run scripts/sysex_spike.py.
"""

import argparse
import json
import shutil
import sys
import uuid
from importlib import metadata
from pathlib import Path

import mido
from sysex_spike import REQUEST_PORT, RESPONSE_PORT, FLLink

REPO = Path(__file__).resolve().parent.parent
SPIKE = REPO / "fl_scripts" / "spike"
MAILBOX = Path.home() / ".fl-mcp"
FL_USER_DATA = Path.home() / "Documents" / "Image-Line" / "FL Studio"
FL_SETTINGS = FL_USER_DATA / "Settings"
PR_DIR = FL_SETTINGS / "Piano roll scripts"
PR_SUBDIR = PR_DIR / "FLMCP Spike"
HARDWARE = FL_SETTINGS / "Hardware"
SPIKE_FILES = {
    SPIKE / "device_FLMCPSpike.py": HARDWARE / "FLMCP Spike" / "device_FLMCPSpike.py",
    SPIKE / "device_FLMCPSysexSpike.py": (
        HARDWARE / "FLMCP SysEx Spike" / "device_FLMCPSysexSpike.py"
    ),
    SPIKE / "FLMCP_Spike.pyscript": PR_DIR / "FLMCP_Spike.pyscript",
}
# The piano roll spike reads the nonce in each place and saves its report in the
# first place that accepts it. Labels match the spike's own labels.
NONCE_FILES = {
    "own_subdir": PR_SUBDIR / "spike_input.json",
    "own_folder": PR_DIR / "FLMCP_spike_input.json",
    "mailbox": MAILBOX / "spike_input.json",
}
REPORT_FILES = [path.parent / "spike_pianoroll.json" for path in NONCE_FILES.values()]
# What the notes design needs from one folder: FL reads our file and writes a reply.
NOTES_OPS = ("read", "write")

results: list[bool] = []


def report(status: str, message: str) -> None:
    results.append(status == "OK")
    print(f"[{status:^4}] {message}")


def check_python() -> None:
    version = ".".join(map(str, sys.version_info[:3]))
    report("OK" if sys.version_info[:2] == (3, 12) else "FAIL", f"Python {version}")


def check_packages() -> None:
    for name in ("mcp", "mido", "python-rtmidi", "fl-studio-api-stubs"):
        try:
            version = metadata.version(name)
        except metadata.PackageNotFoundError:
            report("FAIL", f"{name} not installed (run `uv sync`)")
            continue
        ok = not (name == "mcp" and not version.startswith("2."))
        report("OK" if ok else "FAIL", f"{name} {version}")


def check_ports() -> None:
    outputs, inputs = mido.get_output_names(), mido.get_input_names()
    for name, role in ((REQUEST_PORT, "Mac -> FL"), (RESPONSE_PORT, "FL -> Mac")):
        if name in outputs and name in inputs:
            report("OK", f"MIDI port {name} ({role})")
        else:
            report(
                "FAIL",
                f"MIDI port {name} missing. Audio MIDI Setup > IAC Driver > Ports: "
                "add it and tick 'Device is online'.",
            )


def check_sysex() -> None:
    try:
        with FLLink() as link:
            result = link.request("ping", timeout=2.0)
    except TimeoutError:  # must come first: TimeoutError is a subclass of OSError
        report(
            "TODO",
            "SysEx: no reply from FL. In FL: Options > MIDI Settings, input FLMCP-REQ: "
            "Controller type 'FLMCP SysEx Spike', enabled, Port 10; output FLMCP-RES: "
            "enabled, Port 10.",
        )
        return
    except OSError as exc:
        report("FAIL", f"SysEx: could not open the IAC ports ({exc})")
        return
    info = result.reply.get("result", {})
    report(
        "OK" if result.reply.get("ok") else "FAIL",
        f"SysEx round trip {result.rtt_ms:.1f} ms: FL API {info.get('api_version')}, "
        f"tempo {info.get('tempo')}, PPQ {info.get('ppq')}. "
        "Sizes and latency: uv run scripts/sysex_spike.py",
    )


def write_nonces() -> str:
    """One nonce, written everywhere the piano roll spike looks for it."""
    MAILBOX.mkdir(exist_ok=True)
    PR_SUBDIR.mkdir(parents=True, exist_ok=True)  # FL scripts can't create folders
    source = NONCE_FILES["mailbox"]
    nonce = json.loads(source.read_text())["nonce"] if source.exists() else uuid.uuid4().hex
    for path in NONCE_FILES.values():
        path.write_text(json.dumps({"nonce": nonce}))
    return nonce


def check_pianoroll(nonce: str) -> None:
    found = [path for path in REPORT_FILES if path.exists()]
    if not found:
        report(
            "TODO",
            "Piano roll spike has no report yet. In FL: open a piano roll, then its "
            "Scripting menu > FLMCP_Spike. If the popup says it could not save the "
            "report, paste the popup to Claude.",
        )
        return
    path = max(found, key=lambda p: p.stat().st_mtime)
    data = json.loads(path.read_text())
    ops, nonces = data.get("ops", {}), data.get("nonces", {})
    usable = [
        label for label in NONCE_FILES if all(ops.get(f"{label}.{op}") == "ok" for op in NOTES_OPS)
    ]
    if "spike_error" in data:
        report("FAIL", f"Piano roll spike stopped early: {data['spike_error']}")
    elif not usable:
        report("FAIL", "Piano roll spike: no folder allows both reading and writing")
    elif any(nonces.get(label) != nonce for label in usable):
        report("FAIL", "Piano roll spike: read an old nonce (stale run?). Run it again.")
    else:
        report(
            "OK",
            f"Piano roll spike (PPQ {data.get('ppq')}): read + write work in "
            f"{', '.join(usable)}. Report: {path}",
        )
    for op, result in ops.items():
        print(f"         {op}: {'ok' if result == 'ok' else 'BLOCKED  ' + result}")


def clean_probe_leftovers() -> None:
    """Probe files the FL scripts could not delete themselves (os.remove is blocked)."""
    removed = 0
    for folder in (PR_SUBDIR, PR_DIR, MAILBOX, FL_USER_DATA):
        for name in ("flmcp_probe.tmp", "flmcp_probe.json"):
            if (folder / name).exists():
                (folder / name).unlink()
                removed += 1
        for probe_dir in [*folder.glob("flmcp_mkdir_probe_*"), *folder.glob("mkdir_probe_*")]:
            try:
                probe_dir.rmdir()
                removed += 1
            except OSError:
                pass
    if removed:
        print(f"(removed {removed} leftover probe files)")


def install_spike() -> None:
    for src, dest in SPIKE_FILES.items():
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dest)
        print(f"copied {src.relative_to(REPO)} -> {dest}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--install", action="store_true", help="copy spike scripts into FL")
    args = parser.parse_args()

    if args.install:
        install_spike()
    check_python()
    check_packages()
    check_ports()
    nonce = write_nonces()
    check_sysex()
    check_pianoroll(nonce)
    clean_probe_leftovers()

    passed = sum(results)
    print(f"\n{passed}/{len(results)} Phase 0 checks pass.")
    return 0 if all(results) else 1


if __name__ == "__main__":
    sys.exit(main())
