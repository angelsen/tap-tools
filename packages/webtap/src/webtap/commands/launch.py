"""Chrome and Android device launch commands."""

import signal
import shutil
import subprocess
import sys
import time
from pathlib import Path
from typing import Annotated

import typer

from webtap.app import app
from webtap.commands._builders import success_response, error_response
from webtap.utils.ports import find_available_port, is_port_available


def _register_port_with_daemon(state, port: int) -> dict | None:
    """Register port with daemon, return result or None if daemon unavailable."""
    try:
        result = state.client.call("ports.add", port=port)
        if result.get("status") == "unreachable":
            print(f"Warning: {result.get('warning', 'Port unreachable')}")
        return result
    except Exception as e:
        print(f"Warning: Could not register port with daemon: {e}")
        return None


def _unregister_port(state, port: int) -> None:
    """Unregister port from daemon, ignore errors."""
    try:
        state.client.call("ports.remove", port=port)
    except Exception:
        pass


@app.command(
    display="markdown",
    typer={"name": "run-chrome", "help": "Launch Chrome with debugging enabled"},
    fastmcp={"enabled": False},
)
def run_chrome(
    state,
    port: Annotated[
        int | None, typer.Option("--port", "-p", help="Debugging port (auto-assigns from 37650+ if not set)")
    ] = None,
    private: Annotated[bool, typer.Option("--private", help="Launch in incognito mode")] = False,
) -> dict:
    """Launch Chrome with debugging enabled. Blocks until Ctrl+C.

    Args:
        port: Debugging port (auto-assigns from 37650+ if not set)
        private: Launch in incognito mode

    Returns:
        Status message when Chrome exits
    """
    # Auto-assign port or validate explicit port
    if port is None:
        port = find_available_port()
        if port is None:
            return error_response("No available port in range 37650-37669")
    elif not is_port_available(port):
        return error_response(
            f"Port {port} already in use",
            suggestions=[
                "Omit --port to auto-assign: webtap run-chrome",
                "Check existing Chrome: ps aux | grep chrome",
                f"Kill existing: pkill -f 'remote-debugging-port={port}'",
            ],
        )

    # Find Chrome executable
    chrome_paths = [
        "google-chrome-stable",
        "google-chrome",
        "chromium-browser",
        "chromium",
    ]

    chrome_exe = None
    for path in chrome_paths:
        if shutil.which(path):
            chrome_exe = path
            break

    if not chrome_exe:
        return error_response(
            "Chrome not found",
            suggestions=[
                "Install google-chrome-stable: sudo apt install google-chrome-stable",
                "Or install chromium: sudo apt install chromium-browser",
            ],
        )

    # Use clean temp profile for debugging
    temp_config = Path("/tmp/webtap-chrome-debug")
    temp_config.mkdir(parents=True, exist_ok=True)

    # Launch Chrome (blocking mode - same process group)
    cmd = [
        chrome_exe,
        f"--remote-debugging-port={port}",
        "--remote-allow-origins=*",
        f"--user-data-dir={temp_config}",
        "--disable-search-engine-choice-screen",
        "--no-first-run",
    ]
    if private:
        cmd.append("--incognito")
    process = subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    # Wait for Chrome to start
    time.sleep(1.0)

    # Register port with daemon
    _register_port_with_daemon(state, port)

    # Setup cleanup handler
    def cleanup(signum, frame):
        process.terminate()
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            process.kill()
        _unregister_port(state, port)
        sys.exit(0)

    signal.signal(signal.SIGINT, cleanup)
    signal.signal(signal.SIGTERM, cleanup)

    # Print status
    print(f"Chrome running on port {port}. Press Ctrl+C to stop.")

    # Block until Chrome exits or signal received
    try:
        returncode = process.wait()
    except KeyboardInterrupt:
        cleanup(None, None)
        returncode = 0

    # Unregister on normal exit
    _unregister_port(state, port)

    if returncode == 0:
        return success_response("Chrome closed normally")
    else:
        return error_response(f"Chrome exited with code {returncode}")


def _get_connected_devices() -> list[tuple[str, str]]:
    """Get connected Android devices via adb.

    Returns:
        List of (serial, state) tuples for connected devices
    """
    try:
        result = subprocess.run(
            ["adb", "devices"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        if result.returncode != 0:
            return []

        devices = []
        for line in result.stdout.strip().split("\n")[1:]:  # Skip header
            if line.strip():
                parts = line.split("\t")
                if len(parts) >= 2 and parts[1] == "device":
                    devices.append((parts[0], parts[1]))
        return devices
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return []


def _get_device_name(serial: str) -> str:
    """Get device model name via adb."""
    try:
        result = subprocess.run(
            ["adb", "-s", serial, "shell", "getprop", "ro.product.model"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        if result.returncode == 0:
            return result.stdout.strip() or serial
    except (subprocess.TimeoutExpired, FileNotFoundError):
        pass
    return serial


@app.command(
    display="markdown",
    typer={"name": "setup-android", "help": "Set up Android device debugging"},
    fastmcp={"enabled": False},
)
def setup_android(
    state,
    yes: Annotated[bool, typer.Option("-y", "--yes", help="Auto-configure without prompts")] = False,
    port: Annotated[
        int | None, typer.Option("-p", "--port", help="Local port (auto-assigns from 37650+ if not set)")
    ] = None,
    device: Annotated[str | None, typer.Option("-d", "--device", help="Device serial")] = None,
) -> dict:
    """Set up Android device for Chrome debugging.

    Args:
        yes: Auto-configure without prompts (default: False)
        port: Local port (auto-assigns from 37650+ if not set)
        device: Device serial number (required if multiple devices connected)

    Returns:
        Status message with setup instructions or result
    """
    from webtap.commands._builders import info_response

    # If no -y flag, show setup instructions
    if not yes:
        return info_response(
            title="Android Debugging Setup",
            fields={
                "Step 1": "Enable USB debugging on your Android device",
                "Step 2": "Install adb: sudo apt install adb",
                "Step 3": "Connect device via USB",
                "Step 4": "Accept the debugging prompt on device",
            },
            tips=[
                "webtap setup-android -y  # auto-configure (port 37650+)",
                "webtap setup-android -y -p 9222  # explicit port",
            ],
        )

    # Check if adb is installed
    if not shutil.which("adb"):
        return error_response(
            "adb not found",
            suggestions=[
                "Install: sudo apt install adb",
                "Or: sudo pacman -S android-tools",
            ],
        )

    # Auto-assign port or validate explicit port
    if port is None:
        port = find_available_port()
        if port is None:
            return error_response("No available port in range 37650-37669")
    elif not is_port_available(port):
        return error_response(
            f"Port {port} already in use",
            suggestions=[
                "Omit -p to auto-assign: webtap setup-android -y",
                f"Check: lsof -i :{port}",
            ],
        )

    # Get connected devices
    devices = _get_connected_devices()

    if len(devices) == 0:
        return error_response(
            "No Android devices connected",
            suggestions=[
                "Connect device via USB",
                "Enable USB debugging in Developer Options",
                "Run: adb devices",
            ],
        )

    # Handle device selection
    if len(devices) == 1:
        target_device = devices[0][0]
    elif device:
        # User specified device
        device_serials = [d[0] for d in devices]
        if device not in device_serials:
            return error_response(
                f"Device '{device}' not found",
                suggestions=[f"Available devices: {', '.join(device_serials)}"],
            )
        target_device = device
    else:
        # Multiple devices, no selection
        device_serials = [d[0] for d in devices]
        return error_response(
            "Multiple devices connected. Specify with --device/-d",
            suggestions=[f"webtap setup-android -y -d {d}" for d in device_serials],
        )

    # Get device name for display
    device_name = _get_device_name(target_device)

    # Run adb forward
    try:
        result = subprocess.run(
            ["adb", "-s", target_device, "forward", f"tcp:{port}", "localabstract:chrome_devtools_remote"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        if result.returncode != 0:
            return error_response(
                f"adb forward failed: {result.stderr.strip()}",
                suggestions=[
                    "Ensure Chrome is running on the device",
                    "Try: adb kill-server && adb start-server",
                ],
            )
    except subprocess.TimeoutExpired:
        return error_response("adb forward timed out")

    # Register port with daemon
    _register_port_with_daemon(state, port)

    # Setup cleanup handler
    def cleanup(signum, frame):
        # Remove adb forward
        subprocess.run(
            ["adb", "-s", target_device, "forward", "--remove", f"tcp:{port}"],
            capture_output=True,
            timeout=5,
        )
        _unregister_port(state, port)
        sys.exit(0)

    signal.signal(signal.SIGINT, cleanup)
    signal.signal(signal.SIGTERM, cleanup)

    # Print status and block
    print(f"Android debugging active: {device_name} on port {port}. Press Ctrl+C to stop.")

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        cleanup(None, None)

    return success_response("Android debugging stopped")


__all__ = ["run_chrome", "setup_android"]
