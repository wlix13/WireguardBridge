"""Process manager for WireGuard Bridge."""

import asyncio
import json
import os
import signal
import time
from pathlib import Path
from typing import Any

from bridge.logger import LOG
from bridge.models import ProcessConfig, ProcessInfo, ProcessState


class ProcessManager:
    """Manages multiple processes with health checking and automatic restart."""

    def __init__(self):
        self.processes: dict[str, ProcessInfo] = {}
        self.running = False
        self.shutdown_event = asyncio.Event()
        self._tasks: list[asyncio.Task] = []
        self.status_file = Path(os.environ.get("STATUS_FILE", "/run/process_status.json"))

    async def add_process(self, config: ProcessConfig) -> None:
        """Add a process to be managed."""

        if config.name in self.processes:
            raise ValueError(f"Process '{config.name}' already exists")

        self.processes[config.name] = ProcessInfo(config=config)
        LOG.info(f"Added process '{config.name}' to manager")

    async def start_process(self, name: str) -> bool:
        """Start a specific process."""

        if name not in self.processes:
            LOG.error(f"Process '{name}' not found")
            return False

        process_info = self.processes[name]
        config = process_info.config

        if process_info.state in [ProcessState.RUNNING, ProcessState.STARTING]:
            LOG.warning(f"Process '{name}' is already running or starting")
            return True

        for dep_name in config.dependencies:
            if dep_name not in self.processes:
                LOG.error(f"Dependency '{dep_name}' not found for process '{name}'")
                return False

            dep_info = self.processes[dep_name]
            if dep_info.state != ProcessState.RUNNING:
                LOG.error(f"Dependency '{dep_name}' is not running for process '{name}'")
                return False

        if config.dependencies:
            LOG.info(f"Waiting for {len(config.dependencies)} dependencies for process '{name}' to be healthy...")
            await self._wait_for_dependencies_healthy(name)

        LOG.info(f"Starting process '{name}': {' '.join(config.command)}")
        process_info.state = ProcessState.STARTING

        try:
            env = config.env.copy() if config.env else {}

            if config.start_delay > 0:
                LOG.info(f"Waiting {config.start_delay}s before starting '{name}'")
                await asyncio.sleep(config.start_delay)

            process = await asyncio.create_subprocess_exec(
                *config.command,
                cwd=config.cwd,
                env=env,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )

            process_info.process = process
            process_info.pid = process.pid
            process_info.start_time = time.time()
            process_info.state = ProcessState.RUNNING

            LOG.success(f"Process '{name}' started with PID {process.pid}")

            monitor_task = asyncio.create_task(self._monitor_process(name))
            self._tasks.append(monitor_task)

            return True

        except Exception as e:
            LOG.error(f"Failed to start process '{name}': {e}")
            process_info.state = ProcessState.FAILED
            return False

    async def _update_status_file(self) -> None:
        """Periodically write the status of all processes to a file."""

        while self.running:
            try:
                status_data = self.get_all_status()
                with open(self.status_file, "w") as f:
                    json.dump(status_data, f)
            except Exception as e:
                LOG.error(f"Failed to write process status file: {e}")

            await asyncio.sleep(5)

    async def _wait_for_dependencies_healthy(self, name: str, timeout: int = 60) -> None:
        """Wait for all dependencies to be healthy before starting a process."""

        process_info = self.processes[name]
        config = process_info.config

        for dep_name in config.dependencies:
            dep_info = self.processes[dep_name]
            dep_config = dep_info.config

            if dep_config.health_check:
                LOG.info(f"Waiting for dependency '{dep_name}'")

                for i in range(timeout):
                    if dep_info.state != ProcessState.RUNNING:
                        raise RuntimeError(f"Dependency '{dep_name}' stopped unexpectedly")

                    try:
                        if dep_config.health_check():
                            LOG.success(f"Dependency '{dep_name}' is healthy")
                            break
                    except Exception as e:
                        LOG.warning(f"Health check error for '{dep_name}': {e}")

                    if i % 10 == 0:
                        LOG.info(f"Still waiting for '{dep_name}' to be healthy... ({i}/{timeout})")

                    await asyncio.sleep(1)
                else:
                    raise RuntimeError(f"Dependency '{dep_name}' did not become healthy within timeout")
            else:
                LOG.info(f"Dependency '{dep_name}' has no health check, assuming healthy")

    async def stop_process(self, name: str, force: bool = False) -> bool:
        """Stop a specific process."""

        process_info = self.processes.get(name)
        if not process_info:
            LOG.error(f"Process '{name}' not found")
            return False

        # If already stopped, or no process object, or process already exited, handle and return early
        if process_info.state == ProcessState.STOPPED:
            LOG.info(f"Process '{name}' is already stopped")
            return True

        proc = process_info.process
        if not proc or proc.returncode is not None:
            if not proc:
                LOG.warning(f"No process object for '{name}', marking as stopped")
            else:
                LOG.info(f"Process '{name}' has already exited. Cleaning up.")
            process_info.state = ProcessState.STOPPED
            process_info.process = None
            process_info.pid = None
            return True

        LOG.info(f"Stopping process '{name}' (PID: {process_info.pid})")
        process_info.state = ProcessState.STOPPING

        try:
            proc.terminate()
            try:
                await asyncio.wait_for(proc.wait(), timeout=process_info.config.stop_timeout)
                LOG.info(f"Process '{name}' stopped gracefully")
            except TimeoutError:
                if not force:
                    LOG.error(f"Process '{name}' did not stop within timeout")
                    return False
                LOG.warning(f"Force killing process '{name}'")
                proc.kill()
                await proc.wait()

            process_info.state = ProcessState.STOPPED
            process_info.process = None
            process_info.pid = None
            return True

        except Exception as e:
            LOG.error(f"Error stopping process '{name}': {e}")
            return False

    async def restart_process(self, name: str) -> bool:
        """Restart a specific process."""

        LOG.info(f"Restarting process '{name}'")

        if await self.stop_process(name, force=True):
            process_info = self.processes[name]
            backoff_delay = min(2**process_info.restart_count, 30)  # Max 30 seconds

            if backoff_delay > 0:
                LOG.info(f"Backoff delay {backoff_delay}s before restarting '{name}'")
                process_info.state = ProcessState.BACKOFF
                await asyncio.sleep(backoff_delay)

            process_info.restart_count += 1
            process_info.last_restart = time.time()

            return await self.start_process(name)

        return False

    async def _monitor_process(self, name: str) -> None:
        """Monitor a process and handle restarts."""

        process_info = self.processes[name]
        config = process_info.config

        try:
            if process_info.process:
                return_code = await process_info.process.wait()
            else:
                return

            LOG.warning(f"Process '{name}' exited with code {return_code}")

            if (
                config.auto_restart
                and process_info.restart_count < config.start_retries
                and not self.shutdown_event.is_set()
            ):
                LOG.info(
                    f"Auto-restarting process '{name}' "
                    f"(attempt {process_info.restart_count + 1}/{config.start_retries})"
                )
                await self.restart_process(name)
            else:
                LOG.error(f"Process '{name}' failed permanently or restart limit reached")
                process_info.state = ProcessState.FAILED

        except Exception as e:
            LOG.error(f"Error monitoring process '{name}': {e}")
            process_info.state = ProcessState.FAILED

    async def start_all(self) -> bool:
        """Start all processes in priority order, skipping already running ones."""

        LOG.info("Starting all processes...")

        # Sort processes by priority (lower number = higher priority)
        sorted_processes = sorted(self.processes.items(), key=lambda x: x[1].config.priority)

        success = True
        for name, process_info in sorted_processes:
            if process_info.state == ProcessState.RUNNING:
                LOG.info(f"Process '{name}' is already running, skipping")
                continue

            if not await self.start_process(name):
                LOG.error(f"Failed to start process '{name}'")
                success = False

        return success

    async def stop_all(self, force: bool = False) -> bool:
        """Stop all processes in reverse priority order."""

        LOG.info("Stopping all processes...")

        # Sort processes by reverse priority (higher number = stop first)
        sorted_processes = sorted(self.processes.items(), key=lambda x: x[1].config.priority, reverse=True)

        success = True
        for name, process_info in sorted_processes:
            if process_info.state == ProcessState.RUNNING:
                if not await self.stop_process(name, force=force):
                    LOG.error(f"Failed to stop process '{name}'")
                    success = False

        return success

    async def run(self) -> None:
        """Main run loop for the process manager."""

        self.running = True

        self._setup_signal_handlers()

        try:
            LOG.info("Process manager starting...")

            status_task = asyncio.create_task(self._update_status_file())
            self._tasks.append(status_task)

            await self.start_all()

            await self.shutdown_event.wait()

        except Exception as e:
            LOG.error(f"Process manager error: {e}")
        finally:
            self.running = False
            await self.cleanup()

    def _setup_signal_handlers(self) -> None:
        """Setup signal handlers for graceful shutdown."""

        def signal_handler(signum: int) -> None:
            LOG.info(f"Received signal {signum}, initiating shutdown...")
            self.shutdown_event.set()

        signal.signal(signal.SIGTERM, lambda s, f: signal_handler(s))
        signal.signal(signal.SIGINT, lambda s, f: signal_handler(s))

    async def cleanup(self) -> None:
        """Cleanup resources and stop all processes."""

        LOG.info("Cleaning up process manager...")

        self.status_file.unlink(missing_ok=True)

        for task in self._tasks:
            if not task.done():
                task.cancel()

        if self._tasks:
            await asyncio.gather(*self._tasks, return_exceptions=True)

        await self.stop_all(force=True)

        LOG.info("Process manager cleanup completed")

    def get_process_status(self, name: str) -> dict[str, Any] | None:
        """Get status information for a process."""

        if name not in self.processes:
            return None

        process_info = self.processes[name]
        return {
            "name": name,
            "state": process_info.state.value,
            "pid": process_info.pid,
            "start_time": process_info.start_time,
            "restart_count": process_info.restart_count,
            "last_restart": process_info.last_restart,
            "command": " ".join(process_info.config.command),
            "priority": process_info.config.priority,
        }

    def get_all_status(self) -> dict[str, dict[str, Any]]:
        """Get status information for all processes."""

        result = {}
        for name in self.processes.keys():
            status = self.get_process_status(name)
            if status is not None:
                result[name] = status
        return result
