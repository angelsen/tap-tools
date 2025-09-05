"""Chrome launch commands for WebTap."""

import shutil
import subprocess
from pathlib import Path

from webtap.app import app
from webtap.commands._builders import success_response, error_response


@app.command(
    display="markdown",
    typer={"name": "run-chrome", "help": "Launch Chrome with debugging enabled"},
    fastmcp={"enabled": False},
)
def run_chrome(state, detach: bool = True, port: int = 9222) -> dict:
    """Launch Chrome with debugging enabled for WebTap.

    Args:
        detach: Run Chrome in background (default: True)
        port: Debugging port (default: 9222)

    Returns:
        Status message
    """
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

    # Setup temp profile with symlinks to real profile
    temp_config = Path("/tmp/webtap-chrome-debug")
    real_config = Path.home() / ".config" / "google-chrome"

    if not temp_config.exists():
        temp_config.mkdir(parents=True)

        # Symlink Default profile
        default_profile = real_config / "Default"
        if default_profile.exists():
            (temp_config / "Default").symlink_to(default_profile)

        # Copy essential files
        for file in ["Local State", "First Run"]:
            src = real_config / file
            if src.exists():
                (temp_config / file).write_text(src.read_text())

    # Launch Chrome
    cmd = [chrome_exe, f"--remote-debugging-port={port}", "--remote-allow-origins=*", f"--user-data-dir={temp_config}"]

    if detach:
        subprocess.Popen(cmd, start_new_session=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return success_response(
            f"Launched {chrome_exe}",
            details={
                "Port": str(port),
                "Mode": "Background (detached)",
                "Profile": str(temp_config),
                "Next step": "Run connect() to attach WebTap",
            },
        )
    else:
        result = subprocess.run(cmd)
        if result.returncode == 0:
            return success_response("Chrome closed normally")
        else:
            return error_response(f"Chrome exited with code {result.returncode}")
