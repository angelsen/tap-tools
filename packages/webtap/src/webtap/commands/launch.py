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
from webtap.services.setup.platform import detect_browsers, find_browser_path, SUPPORTED_BROWSERS
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
    typer={"name": "run-browser", "help": "Launch browser with debugging enabled"},
    fastmcp={"enabled": False},
)
def run_browser(
    state,
    port: Annotated[
        int | None, typer.Option("--port", "-p", help="Debugging port (auto-assigns from 37650+ if not set)")
    ] = None,
    private: Annotated[bool, typer.Option("--private", help="Launch in incognito mode")] = False,
    browser: Annotated[str | None, typer.Option("--browser", "-b", help="Browser ID (chrome, edge) or path")] = None,
) -> dict:
    """Launch browser with debugging enabled. Blocks until Ctrl+C.

    Args:
        port: Debugging port (auto-assigns from 37650+ if not set)
        private: Launch in incognito mode
        browser: Browser ID (chrome, edge) or full path (auto-detects if not set)

    Returns:
        Status message when browser exits
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
                "Omit --port to auto-assign: webtap run-browser",
                "Check existing browser: ps aux | grep chrome",
                f"Kill existing: pkill -f 'remote-debugging-port={port}'",
            ],
        )

    # Find browser executable
    if browser:
        # Check if it's a canonical ID first
        browser_path = find_browser_path(browser)
        if browser_path:
            chrome_exe = browser_path
        # Otherwise treat as path/name
        elif shutil.which(browser) or Path(browser).exists():
            chrome_exe = browser if shutil.which(browser) else browser
        else:
            return error_response(
                f"Browser not found: {browser}",
                suggestions=[f"Supported IDs: {', '.join(SUPPORTED_BROWSERS.keys())}"],
            )
    else:
        found = detect_browsers()

        if len(found) == 0:
            return error_response(
                "No supported browser found",
                suggestions=[
                    "Install Chrome: yay -S google-chrome",
                    "Install Edge: yay -S microsoft-edge-stable-bin",
                    "Or specify: webtap run-browser --browser /path/to/browser",
                ],
            )
        elif len(found) > 1:
            return error_response(
                "Multiple browsers found",
                suggestions=[f"webtap run-browser --browser {b}" for b in found],
            )

        chrome_exe = find_browser_path(found[0])

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
    print(f"Browser running on port {port}. Press Ctrl+C to stop.")

    # Block until Chrome exits or signal received
    try:
        returncode = process.wait()
    except KeyboardInterrupt:
        cleanup(None, None)
        returncode = 0

    # Unregister on normal exit
    _unregister_port(state, port)

    if returncode == 0:
        return success_response("Browser closed normally")
    else:
        return error_response(f"Browser exited with code {returncode}")


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
    typer={"name": "debug-android", "help": "Forward Android Chrome for debugging"},
    fastmcp={"enabled": False},
)
def debug_android(
    state,
    yes: Annotated[bool, typer.Option("-y", "--yes", help="Auto-configure without prompts")] = False,
    port: Annotated[
        int | None, typer.Option("-p", "--port", help="Local port (auto-assigns from 37650+ if not set)")
    ] = None,
    device: Annotated[str | None, typer.Option("-d", "--device", help="Device serial")] = None,
) -> dict:
    """Forward Android Chrome for debugging via adb.

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
                "webtap debug-android -y  # auto-configure (port 37650+)",
                "webtap debug-android -y -p 9222  # explicit port",
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
                "Omit -p to auto-assign: webtap debug-android -y",
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
            suggestions=[f"webtap debug-android -y -d {d}" for d in device_serials],
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


__all__ = ["run_browser", "debug_android"]
