#!/usr/bin/env python3
"""Opt-in, unprivileged local Squid lifecycle and privacy-preserving diagnostics."""

import argparse
import fcntl
import logging
from logging.handlers import RotatingFileHandler
import os
from pathlib import Path
import re
import resource
import signal
import socket
import subprocess
import sys
import threading
import time

STATE = Path.home() / ".local/state/devcontainer-squid"
MAX_BYTES = 1024 * 1024
PROXY = "http://127.0.0.1:3128"


def diagnostic(line: str) -> str | None:
    # Never interpolate raw stderr: even fatal parser/request diagnostics may
    # contain credentials or URLs. Unknown messages retain severity only.
    reasons = {
        "permission denied": "Permission denied: check state directory ownership",
        "address already in use": "Port already in use: check the local listener",
        "no such file": "Required file missing: check installation and whitelist",
        "bungled": "Invalid configuration: check squid.conf and whitelist",
        "unrecognized": "Unrecognized configuration directive",
        "no valid signing": "TLS configuration error",
        "cannot open": "Cannot open required file",
        "no dns": "DNS configuration error",
        "accepting http": "Squid listener ready",
        "starting squid": "Squid starting",
        "reconfiguring": "Squid reconfiguring",
        "rotating": "Squid rotating logs",
        "shutting down": "Squid shutting down",
        "exiting normally": "Squid exited normally",
    }
    lowered = line.lower()
    for match, message in reasons.items():
        if match in lowered:
            return message
    for severity in ("fatal", "error", "warning"):
        if severity in lowered:
            return f"Squid {severity}: raw details omitted for credential safety"
    return None


def logger(state: Path) -> logging.Logger:
    result = logging.getLogger("devcontainer-squid")
    if not result.handlers:
        handler = RotatingFileHandler(state / "cache.log", maxBytes=MAX_BYTES, backupCount=3)
        handler.setFormatter(logging.Formatter("%(asctime)s %(message)s"))
        result.addHandler(handler)
        result.setLevel(logging.INFO)
    return result


def whitelist(source: Path) -> str:
    domains = []
    for number, raw in enumerate(source.read_text(encoding="utf-8").splitlines(), 1):
        value = raw.split("#", 1)[0].strip().lower()
        if not value:
            continue
        if not re.fullmatch(r"\.?[a-z0-9](?:[a-z0-9-]*[a-z0-9])?(?:\.[a-z0-9](?:[a-z0-9-]*[a-z0-9])?)+", value) or re.fullmatch(r"[.0-9]+", value):
            raise ValueError(f"whitelist line {number}: expected a domain only (no URL, port, credentials or wildcard)")
        domains.append(value)
    if not domains:
        raise ValueError("whitelist must contain at least one domain")
    return "\n".join(sorted(set(domains))) + "\n"


def configure(state: Path, workspace: Path) -> None:
    # Squid 5's filename directives do not consistently support quoted paths.
    if re.search(r'[\s"\\]', str(state)):
        raise ValueError("state path contains unsupported characters")
    content = whitelist(workspace / ".devcontainer/squid/whitelist.txt")
    (state / "whitelist.txt").write_text(content)
    template = Path(__file__).resolve().with_name("squid.conf").read_text()
    template = template.replace("@STATE@", str(state))
    template = template.replace("@ALLOWLIST@", '"' + str(state / "whitelist.txt") + '"')
    (state / "squid.conf").write_text(template)
    parsed = subprocess.run(["squid", "-f", str(state / "squid.conf"), "-k", "parse"], capture_output=True, text=True)
    for line in parsed.stderr.splitlines():
        message = diagnostic(line)
        if message:
            logger(state).info(message)
    if parsed.returncode:
        raise ValueError("Squid configuration rejected; see cache.log (sanitized diagnostics)")


def running(state: Path) -> int | None:
    try:
        pid = int((state / "supervisor.pid").read_text())
        command = Path(f"/proc/{pid}/cmdline").read_bytes().split(b"\0")
        if b"serve" in command and str(state).encode() in command:
            return pid
    except (OSError, ValueError):
        pass
    return None


def ready(state: Path) -> bool:
    if not running(state) or not (state / "ready").exists():
        return False
    try:
        with socket.create_connection(("127.0.0.1", 3128), timeout=0.2):
            return True
    except OSError:
        return False


def serve(state: Path) -> None:
    # Core files could otherwise retain plaintext HTTP headers in memory.
    resource.setrlimit(resource.RLIMIT_CORE, (0, 0))
    with (state / "supervisor.lock").open("w") as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            return
        (state / "supervisor.pid").write_text(str(os.getpid()))
        (state / "ready").unlink(missing_ok=True)
        log = logger(state)
        stopped = threading.Event()
        signal.signal(signal.SIGTERM, lambda *_: stopped.set())
        signal.signal(signal.SIGINT, lambda *_: stopped.set())
        # Explicitly discard stdout, and classify stderr without writing it raw.
        child = subprocess.Popen(["squid", "-N", "-d1", "-f", str(state / "squid.conf")],
                                 stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, text=True)

        def consume() -> None:
            for line in child.stderr:
                message = diagnostic(line)
                if message:
                    log.info(message)
                if "accepting http" in line.lower():
                    (state / "ready").touch()

        reader = threading.Thread(target=consume, daemon=True)
        reader.start()
        log.info("Supervisor started; raw diagnostics are not retained")
        try:
            while child.poll() is None and not stopped.wait(5):
                access = state / "access.log"
                if access.exists() and access.stat().st_size >= MAX_BYTES:
                    child.send_signal(signal.SIGUSR1)
        finally:
            if child.poll() is None:
                child.terminate()
                try:
                    child.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    child.kill()
                    child.wait()
            reader.join(timeout=2)
            log.info("Squid stopped (exit status %d)", child.returncode)
            (state / "ready").unlink(missing_ok=True)
            (state / "supervisor.pid").unlink(missing_ok=True)


def stop(state: Path) -> None:
    pid = running(state)
    if pid:
        os.kill(pid, signal.SIGTERM)
        for _ in range(120):
            if not running(state):
                return
            time.sleep(0.1)
        raise ValueError("Squid stop timed out; check cache.log")


def start(state: Path) -> None:
    if not (state / "enabled").exists():
        print("Squid disabled; existing network settings unchanged")
        return
    if ready(state):
        return
    if running(state):
        raise ValueError("Squid is starting or unhealthy; check cache.log, then reload")
    workspace = Path((state / "enabled").read_text())
    configure(state, workspace)
    subprocess.Popen([sys.executable, str(Path(__file__).resolve()), "--state", str(state), "serve"],
                     stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                     start_new_session=True)
    for _ in range(100):
        if ready(state):
            print("Squid ready on 127.0.0.1:3128")
            return
        time.sleep(0.1)
    raise ValueError("Squid failed to start; check cache.log and port 3128")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--state", type=Path, default=STATE, help=argparse.SUPPRESS)
    parser.add_argument("action", choices=["enable", "disable", "start", "reload", "status", "denied", "serve"])
    parser.add_argument("--workspace", type=Path, default=Path.cwd())
    args = parser.parse_args()
    state = args.state.resolve()
    os.umask(0o077)
    state.mkdir(parents=True, exist_ok=True, mode=0o700)
    state.chmod(0o700)
    if args.action == "enable":
        configure(state, args.workspace.resolve())
        stop(state)
        (state / "enabled").write_text(str(args.workspace.resolve()))
        start(state)
        print("Open a new terminal; configure VS Code Remote http.proxy separately. See developer-setup.md")
    elif args.action == "disable":
        (state / "enabled").unlink(missing_ok=True)
        stop(state)
        print("Squid disabled. Remove Remote http.proxy, reload VS Code and open a fresh terminal.")
    elif args.action == "reload":
        if not (state / "enabled").exists():
            raise ValueError("Squid is disabled; enable it first")
        # Validate before stopping. A brief restart ensures new ACLs have taken
        # effect and closes CONNECT tunnels admitted by the previous allowlist.
        configure(state, Path((state / "enabled").read_text()))
        stop(state)
        start(state)
    elif args.action == "start":
        start(state)
    elif args.action == "serve":
        serve(state)
    elif args.action == "status":
        print("enabled=" + str((state / "enabled").exists()) + " ready=" + str(ready(state)))
        print("Logs: " + str(state))
    else:
        for path in sorted(state.glob("access.log*")):
            for line in path.read_text().splitlines():
                if "TCP_DENIED/" in line:
                    print(line)


if __name__ == "__main__":
    try:
        main()
    except (OSError, ValueError) as error:
        # Exception strings from the controller contain only local paths or
        # fixed validation reasons, never raw Squid output or whitelist values.
        raise SystemExit(str(error)) from None
