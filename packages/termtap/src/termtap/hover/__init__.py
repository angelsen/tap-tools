"""Hover dialog functionality for termtap."""
import os
import subprocess
import logging
from pathlib import Path
from typing import Optional, Literal
from dataclasses import dataclass

# Set up logger
logger = logging.getLogger(__name__)


@dataclass
class HoverResult:
    """Result from hover dialog."""
    choice: str
    message: Optional[str] = None
    
    @property
    def action(self) -> str:
        """Map choice to action."""
        action_map = {
            "": "execute",      # Enter
            "\n": "execute",    # Enter
            "e": "edit",
            "c": "cancel",
            "j": "join",
            "a": "abort",
            "f": "finish",
            "r": "rerun",
        }
        return action_map.get(self.choice, "cancel")


def show_hover(
    session: str,
    command: str = "",
    mode: Literal["before", "pattern", "during", "complete"] = "before",
    output: str = "",
    pattern: str = "",
    title: Optional[str] = None,
    elapsed: Optional[float] = None
) -> HoverResult:
    """Show hover dialog and return result.
    
    Args:
        session: Session name
        command: Command being executed
        mode: Dialog mode (before, pattern, during, complete)
        output: Current/final output
        pattern: Pattern that triggered (for pattern mode)
        title: Optional custom title
        elapsed: Elapsed time (for complete mode)
        
    Returns:
        HoverResult with choice and optional message
    """
    logger.info(f"show_hover called: mode={mode}, session={session}, pattern={pattern}, command={command[:50]}...")
    # Get dialog script path
    script_path = Path(__file__).parent / "dialog.sh"
    
    if not script_path.exists():
        return HoverResult(choice="c", message="Dialog script not found")
    
    # Set up environment
    env = os.environ.copy()
    env.update({
        "TERMTAP_SESSION": session,
        "TERMTAP_COMMAND": command,
        "TERMTAP_MODE": mode,
        "TERMTAP_OUTPUT": output,
        "TERMTAP_PATTERN": pattern,
        "TERMTAP_TEMP_DIR": "/tmp/termtap",
    })
    
    if title:
        env["TERMTAP_TITLE"] = title
    if elapsed:
        env["TERMTAP_ELAPSED"] = f"{elapsed:.1f}s"
    
    # Run dialog
    try:
        result = subprocess.run(
            [str(script_path)],
            capture_output=True,
            text=True,
            env=env
        )
        
        # Parse output
        choice = "c"  # Default to cancel
        message = None
        
        for line in result.stdout.strip().split('\n'):
            if line.startswith("CHOICE="):
                choice = line[7:]
            elif line.startswith("MESSAGE="):
                message = line[8:]
        
        logger.info(f"Hover dialog returned: choice={choice}, message={message}")
        return HoverResult(choice=choice, message=message)
        
    except Exception as e:
        logger.error(f"Error in show_hover: {e}")
        return HoverResult(choice="c", message=str(e))


def should_hover(command: str, config: dict) -> bool:
    """Check if command should trigger hover based on config."""
    # Explicit hover setting
    if config.get("hover", False):
        return True
        
    # Check hover patterns
    hover_patterns = config.get("hover_patterns", [])
    if any(pattern in command for pattern in hover_patterns):
        return True
        
    # Check dangerous commands
    dangerous = ["rm -rf", "DELETE", "DROP", "> /dev/"]
    if any(d in command for d in dangerous):
        return True
        
    return False


def check_tmux_hover_env() -> bool:
    """Check if hover is enabled via tmux environment."""
    try:
        # Check TERMTAP_HOVER
        result = subprocess.run(
            ["tmux", "show-environment", "TERMTAP_HOVER"],
            capture_output=True,
            text=True
        )
        if result.returncode == 0 and "true" in result.stdout:
            return True
            
        # Check TERMTAP_HOVER_ONCE (and unset it)
        result = subprocess.run(
            ["tmux", "show-environment", "TERMTAP_HOVER_ONCE"],
            capture_output=True,
            text=True
        )
        if result.returncode == 0 and "true" in result.stdout:
            # Unset after reading
            subprocess.run(["tmux", "set-environment", "-u", "TERMTAP_HOVER_ONCE"])
            return True
            
    except Exception:
        pass
        
    return False


def pattern_hover_callback(
    pattern: str,
    output: str,
    session: str,
    command: str
) -> Optional[str]:
    """Callback for pattern detection during execution.
    
    Returns:
        Optional action: "abort", "complete", or None to continue
    """
    logger.info(f"pattern_hover_callback: pattern='{pattern}' detected in output")
    result = show_hover(
        session=session,
        command=command,
        mode="pattern",
        output=output,
        pattern=pattern,
        title=f"Pattern: {pattern}"
    )
    
    if result.action == "abort":
        return "abort"
    elif result.action == "finish":
        return "complete"
    elif result.action == "join":
        # Join session in new window
        os.system(f"tmux new-window -t {session}")
        return None
    else:
        return None  # Continue