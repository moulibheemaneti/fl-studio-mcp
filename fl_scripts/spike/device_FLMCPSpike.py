# name=FLMCP Spike
"""Phase 0 spike: which file operations does FL allow a device script?

FL runs scripts behind a Python audit hook that can block file operations, so
each operation the mailbox needs is tried on its own. The mailbox folder must
already exist (scripts/check_phase0.py creates it).
Results go to ~/.fl-mcp/spike_device.json and to FL's View > Script output.

Imports only json, os and time: importing datetime crashes FL when a script is
reloaded, and tempfile uses os.open, which FL's sandbox rejects.

Throwaway: delete once DECISIONS.md records the result.
"""


def run_spike(env, extra):
    # Kept identical in both spike scripts so the two FL environments are
    # tested the same way.
    import json
    import os
    import sys
    import time

    report = {"env": env, "python": sys.version.split()[0], "ops": {}, "extra": extra}

    def attempt(op, fn):
        try:
            fn()
            report["ops"][op] = "ok"
            return True
        except Exception as exc:
            report["ops"][op] = repr(exc)
            return False

    def write_text(path, text):
        with open(path, "w", encoding="utf-8") as f:
            f.write(text)

    def probe_folder(label, folder):
        tmp = os.path.join(folder, "flmcp_probe.tmp")
        final = os.path.join(folder, "flmcp_probe.json")
        attempt(label + ".write", lambda: write_text(tmp, "{}"))
        replaced = attempt(label + ".replace", lambda: os.replace(tmp, final))
        attempt(label + ".remove", lambda: os.remove(final if replaced else tmp))

    home = os.path.expanduser("~")
    mailbox = os.path.join(home, ".fl-mcp")

    def read_nonce():
        with open(os.path.join(mailbox, "spike_input.json"), encoding="utf-8") as f:
            report["read_nonce"] = json.load(f)["nonce"]

    def probe_mkdir():
        probe_dir = os.path.join(mailbox, f"mkdir_probe_{time.time_ns()}")
        if attempt("mailbox.mkdir", lambda: os.mkdir(probe_dir)):
            attempt("mailbox.rmdir", lambda: os.rmdir(probe_dir))

    try:
        report["mailbox_exists"] = os.path.isdir(mailbox)
        attempt("mailbox.listdir", lambda: os.listdir(mailbox))
        attempt("mailbox.read", read_nonce)
        probe_folder("mailbox", mailbox)
        probe_folder("fl_user_data", os.path.join(home, "Documents", "Image-Line", "FL Studio"))
        probe_mkdir()
    except Exception as exc:
        report["spike_error"] = repr(exc)

    out_path = os.path.join(mailbox, "spike_" + env + ".json")
    if attempt("save_report", lambda: write_text(out_path, json.dumps(report, indent=2))):
        summary = f"FLMCP spike ({env}): wrote {out_path}"
    else:
        summary = f"FLMCP spike ({env}): could not save the report, copy this output instead"

    lines = [summary] + [f"  {op}: {result}" for op, result in report["ops"].items()]
    if "spike_error" in report:
        lines.append(f"  spike_error: {report['spike_error']}")
    message = "\n".join(lines)
    print(message)
    print(report)
    return message


def OnInit():
    extra = {}
    try:
        import general

        extra["fl_api_version"] = general.getVersion()
    except Exception as exc:
        extra["fl_api_version"] = repr(exc)
    run_spike("device", extra)
