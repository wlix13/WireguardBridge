"""Shell wrapper for WireGuard Bridge."""

import subprocess

from bridge.logger import LOG


def run_command(
    command: list[str],
    timeout: int = 30,
    check: bool = True,
    sudo: bool = False,
) -> subprocess.CompletedProcess:
    """Run a command with timeout and error handling."""

    try:
        if sudo:
            command = ["sudo"] + command

        result = subprocess.run(
            command,
            capture_output=True,
            text=True,
            timeout=timeout,
            check=check,
            shell=False,
        )
        return result
    except subprocess.CalledProcessError as e:
        LOG.error(f"Command failed: {' '.join(command)}")
        LOG.error(f"Exit code: {e.returncode}")
        LOG.error(f"Stderr: {e.stderr}")
        raise
    except subprocess.TimeoutExpired:
        LOG.error(f"Command timed out after {timeout}s: {' '.join(command)}")
        raise
