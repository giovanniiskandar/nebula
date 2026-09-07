"""Delivering a banner without letting user input reach a shell."""

import subprocess
from pathlib import Path

from nebula import notify


def test_the_message_is_passed_as_argv_not_interpolated():
    """Allocation names are user input that ends up inside an AppleScript."""
    command = notify.build_command("Nebula", 'Client " & (do shell script "x") & "')
    # The script is not in the command at all -- it is piped in.
    assert not any("display notification" in part for part in command)
    assert command[-1] == 'Client " & (do shell script "x") & "'


def test_the_script_reads_its_arguments():
    assert "on run argv" in notify._SCRIPT
    assert "display notification" in notify._SCRIPT


def test_the_script_is_piped_on_stdin(monkeypatch):
    """`osascript -` reads the script from stdin.

    Passing it as an argument instead makes osascript wait on stdin forever,
    and -- because a closed stdin looks like an empty script -- it exits 0
    having run nothing. Every test here would pass while no banner ever
    appeared, which is exactly what happened once.
    """
    seen: dict[str, object] = {}

    def capture(command, **kwargs):
        seen["command"] = command
        seen["input"] = kwargs.get("input")
        return subprocess.CompletedProcess(args=command, returncode=0)

    monkeypatch.setattr(subprocess, "run", capture)
    notify.send("Nebula", "hello")

    assert seen["input"] == notify._SCRIPT
    assert seen["command"] == ["osascript", "-", "Nebula", "hello"]


def test_an_injection_payload_does_not_execute(tmp_path: Path):
    """The real check: run it and confirm nothing happened."""
    marker = tmp_path / "pwned"
    payload = f'Work " & (do shell script "touch {marker}") & "'
    notify.send("Nebula", payload)
    assert not marker.exists()


def test_send_reports_success():
    assert notify.send("Nebula", "a plain message") is True


def test_a_failure_is_swallowed(monkeypatch):
    """A missing banner must never cost the user their tracking state."""

    def explode(*args, **kwargs):
        raise OSError("osascript is not here")

    monkeypatch.setattr(subprocess, "run", explode)
    assert notify.send("Nebula", "anything") is False


def test_a_timeout_is_swallowed(monkeypatch):
    def hang(*args, **kwargs):
        raise subprocess.TimeoutExpired(cmd="osascript", timeout=5)

    monkeypatch.setattr(subprocess, "run", hang)
    assert notify.send("Nebula", "anything") is False


def test_a_nonzero_exit_reports_failure(monkeypatch):
    monkeypatch.setattr(
        subprocess,
        "run",
        lambda *a, **k: subprocess.CompletedProcess(args=[], returncode=1),
    )
    assert notify.send("Nebula", "anything") is False
