"""Real Squid, local origin only: SQUID_INTEGRATION=1 python -m pytest ..."""

from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import os
from pathlib import Path
import shutil
import socket
import subprocess
import sys
import threading
import time

import pytest

HERE = Path(__file__).parent
pytestmark = pytest.mark.skipif(os.environ.get("SQUID_INTEGRATION") != "1" or not shutil.which("squid"),
                                reason="opt-in real Squid integration (no external network)")


class Origin(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"local origin ok")

    def log_message(self, *_args):
        pass


def wait_for(predicate):
    for _ in range(100):
        if predicate():
            return
        time.sleep(0.1)
    raise AssertionError("condition did not become true")


def test_real_squid_lifecycle_acl_logs_and_rotation(tmp_path):
    origin = ThreadingHTTPServer(("127.0.0.1", 0), Origin)
    thread = threading.Thread(target=origin.serve_forever, daemon=True)
    thread.start()
    port = origin.server_port
    workspace = tmp_path / "workspace"
    source = workspace / ".devcontainer/squid"
    source.mkdir(parents=True)
    shutil.copy(HERE / "proxy.py", source)
    hosts = tmp_path / "hosts"
    hosts.write_text("127.0.0.1 allowed.test denied.test\n")
    # Only the fixture uses a high local origin port and synthetic DNS.
    config = (HERE / "squid.conf").read_text().replace("port 80\n", f"port {port}\n").replace("port 443\n", f"port {port}\n")
    (source / "squid.conf").write_text(config + f'\nhosts_file {hosts}\n')
    allowed = source / "whitelist.txt"
    allowed.write_text("allowed.test\n")
    state = tmp_path / "state"

    def control(action):
        result = subprocess.run([sys.executable, str(source / "proxy.py"), "--state", str(state),
                                 action, "--workspace", str(workspace)], capture_output=True, text=True, timeout=30)
        assert result.returncode == 0, result.stderr
        return result.stdout

    def request(host, connect=False):
        with socket.create_connection(("127.0.0.1", 3128), timeout=5) as client:
            if connect:
                client.sendall(f"CONNECT {host}:{port} HTTP/1.1\r\nHost: {host}:{port}\r\n\r\n".encode())
                header = b""
                while b"\r\n\r\n" not in header:
                    chunk = client.recv(4096)
                    assert chunk, "proxy closed before sending CONNECT response"
                    header += chunk
                if b"200 Connection established" not in header:
                    return header
                client.sendall(b"GET / HTTP/1.0\r\n\r\n")
            else:
                client.sendall((f"GET http://user:canary-user@{host}:{port}/canary-path?q=canary-query HTTP/1.0\r\n"
                                f"Host: {host}:{port}\r\nAuthorization: Bearer canary-auth\r\n"
                                "Cookie: canary-cookie\r\n\r\n").encode())
            response = b""
            while chunk := client.recv(4096):
                response += chunk
            return response

    try:
        assert "disabled" in control("start")
        control("enable")
        assert "ready=True" in control("status")
        assert b"200 OK" in request("allowed.test")
        assert b"403 Forbidden" in request("denied.test")
        assert b"200 OK" in request("allowed.test", connect=True)
        assert b"403 Forbidden" in request("denied.test", connect=True)
        assert b"403 Forbidden" in request("127.0.0.1")
        for target, method in (("allowed.test:22", "CONNECT"), ("http://allowed.test:22/", "GET")):
            with socket.create_connection(("127.0.0.1", 3128), timeout=5) as client:
                client.sendall(f"{method} {target} HTTP/1.0\r\n\r\n".encode())
                assert b"403 Forbidden" in client.recv(4096)
        wait_for(lambda: "TCP_DENIED/403" in (state / "access.log").read_text())
        assert "denied.test" in control("denied")
        assert "Squid listener ready" in (state / "cache.log").read_text()
        for path in state.glob("*.log*"):
            assert "canary-" not in path.read_text()
        # Both opening and revoking an allowlist entry take effect on reload.
        allowed.write_text("denied.test\n")
        control("reload")
        assert b"200 OK" in request("denied.test")
        assert b"403 Forbidden" in request("allowed.test")
        # Trigger the supervisor's size-based rotation without internet traffic.
        with (state / "access.log").open("a") as stream:
            stream.write("x" * (1024 * 1024))
        wait_for(lambda: (state / "access.log.0").exists())
        assert b"200 OK" in request("denied.test")
        control("disable")
        assert "ready=False" in control("status")
        assert "disabled" in control("start")
        # The ordinary development connection remains available when disabled.
        with socket.create_connection(("127.0.0.1", port), timeout=5) as direct:
            direct.sendall(b"GET / HTTP/1.0\r\n\r\n")
            assert b"200 OK" in direct.recv(4096)
    finally:
        control("disable")
        origin.shutdown()
        origin.server_close()
