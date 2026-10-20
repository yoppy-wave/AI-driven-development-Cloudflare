"""Unit tests require no Squid binary or external network."""

import importlib.util
from pathlib import Path
import subprocess
import sys
from unittest.mock import patch

import pytest

HERE = Path(__file__).parent
SPEC = importlib.util.spec_from_file_location("dev_proxy", HERE / "proxy.py")
proxy = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(proxy)


def test_whitelist_domains_and_comments(tmp_path):
    source = tmp_path / "whitelist.txt"
    source.write_text("# sample\nEXAMPLE.com\n.api.example.com # subdomains\nexample.com\n")
    assert proxy.whitelist(source) == ".api.example.com\nexample.com\n"


@pytest.mark.parametrize("value", ["", "*", ".com", "*.example.com", "http://example.com", "example.com:443",
                                   "127.0.0.1", "user:canary@example.com", "example.com/path?key=canary"])
def test_invalid_whitelist_rejected_without_echoing_value(tmp_path, value):
    source = tmp_path / "whitelist.txt"
    source.write_text(value)
    with pytest.raises(ValueError) as caught:
        proxy.whitelist(source)
    assert "canary" not in str(caught.value)


@pytest.mark.parametrize("raw,expected", [
    ("FATAL: Permission denied https://user:canary@example.com/?q=canary", "Permission denied"),
    ("ERROR: Authorization: Bearer canary", "Squid error"),
    ("WARNING: Cookie: canary", "Squid warning"),
    ("Accepting HTTP Socket connections", "Squid listener ready"),
    ("Bungled config line contains canary", "Invalid configuration"),
])
def test_diagnostics_never_preserve_raw_values(raw, expected):
    result = proxy.diagnostic(raw)
    assert result.startswith(expected)
    assert "canary" not in result


def test_unknown_diagnostics_discarded():
    assert proxy.diagnostic("https://example.com/?key=canary") is None


def test_cache_log_rotates_with_three_backups(tmp_path):
    log = proxy.logger(tmp_path)
    try:
        handler = log.handlers[0]
        handler.maxBytes = 100
        for _ in range(30):
            log.info("Fixed diagnostic message for rotation test")
        assert len(list(tmp_path.glob("cache.log*"))) == 4
        assert handler.backupCount == 3
    finally:
        for handler in log.handlers[:]:
            handler.close()
            log.removeHandler(handler)


def test_parse_failure_is_safe_and_actionable(tmp_path):
    state = tmp_path / "state"
    state.mkdir()
    source = tmp_path / ".devcontainer/squid"
    source.mkdir(parents=True)
    (source / "whitelist.txt").write_text("example.com\n")
    failed = subprocess.CompletedProcess([], 1, "", "FATAL: Bungled config canary-value")
    with patch.object(proxy.subprocess, "run", return_value=failed):
        with pytest.raises(ValueError, match="configuration rejected"):
            proxy.configure(state, tmp_path)
    assert "canary-value" not in (state / "cache.log").read_text()
    for handler in proxy.logger(state).handlers[:]:
        handler.close()
        proxy.logger(state).removeHandler(handler)


def test_disabled_start_does_not_launch_squid(tmp_path):
    with patch.object(proxy.subprocess, "Popen") as launch:
        proxy.start(tmp_path)
    launch.assert_not_called()


def test_stale_pid_not_signalled(tmp_path):
    (tmp_path / "supervisor.pid").write_text(str(__import__("os").getpid()))
    assert proxy.running(tmp_path) is None
    with patch.object(proxy.os, "kill") as kill:
        proxy.stop(tmp_path)
    kill.assert_not_called()


def test_shell_disabled_preserves_existing_proxy(tmp_path):
    result = subprocess.run(["bash", "-c", '. "$1"; test "$HTTP_PROXY" = "http://company.invalid:8080"',
                             "bash", str(HERE / "proxy-env.sh")],
                            env={"HOME": str(tmp_path), "HTTP_PROXY": "http://company.invalid:8080"})
    assert result.returncode == 0


def test_shell_enabled_sets_both_cases(tmp_path):
    state = tmp_path / ".local/state/devcontainer-squid"
    state.mkdir(parents=True)
    (state / "enabled").touch()
    script = '. "$1"; test "$HTTP_PROXY" = "$https_proxy" && test "$NO_PROXY" = "localhost,127.0.0.1,::1"'
    assert subprocess.run(["bash", "-c", script, "bash", str(HERE / "proxy-env.sh")], env={"HOME": str(tmp_path)}).returncode == 0


def test_config_has_deny_default_safe_ports_and_host_only_logs():
    config = (HERE / "squid.conf").read_text()
    assert "http_port 127.0.0.1:3128" in config
    assert "http_access deny all" in config
    assert "acl http_ports port 80" in config
    assert "acl ssl_ports port 443" in config
    assert "dstdomain -n" in config
    assert "cache deny all" in config
    assert "cache_log /dev/null" in config
    logformat = next(line for line in config.splitlines() if line.startswith("logformat "))
    assert logformat == "logformat host_only %ts.%03tu %>rd %>rP %Ss/%03>Hs"


def test_cli_disabled_works_without_squid(tmp_path):
    result = subprocess.run([sys.executable, str(HERE / "proxy.py"), "--state", str(tmp_path), "start"],
                            capture_output=True, text=True)
    assert result.returncode == 0
    assert "disabled" in result.stdout
    assert not (tmp_path / "enabled").exists()
