"""Examples for the tmux-native popup system.

Import and run these in the termtap REPL:
    >>> from termtap.popup.examples import *
    >>> basic_popup()
"""

from termtap.popup import Popup, quick_confirm, quick_choice, quick_input


def basic_popup():
    """Simple popup with styled messages."""
    p = Popup(title="Basic Example")
    p.header("System Status")
    p.info("All services running")
    p.success("Database connected")
    p.warning("High memory usage")
    p.error("Backup failed")
    p.show()


def choice_with_values():
    """Choice dialog with value/display separation."""
    p = Popup(title="Action Selector")
    p.header("SSH Command")
    p.info("Choose an action for remote host")

    choice = p.choose(
        [("exec", "Execute"), ("edit", "Edit Command"), ("save", "Save for Later"), ("abort", "Abort")],
        header="Select action:",
    )

    print(f"Value returned: '{choice}'")
    return choice


def table_selection():
    """Table with selectable rows."""
    p = Popup(title="Process Manager")

    rows = [
        ["1234", "nginx", "active", "3.2M", "0.5%"],
        ["5678", "postgres", "active", "125M", "2.1%"],
        ["9012", "redis", "inactive", "45M", "0.0%"],
        ["3456", "python", "active", "89M", "1.3%"],
    ]

    # Return full row
    full_row = p.table(rows, headers=["PID", "Process", "Status", "Memory", "CPU"], border="rounded")
    print(f"Full row: {full_row}")

    # Return just process name (column 2, 1-indexed)
    process = p.table(rows, headers=["PID", "Process", "Status", "Memory", "CPU"], return_column=2)
    print(f"Process only: {process}")

    return process


def ssh_workflow():
    """SSH command edit workflow - simpler pattern."""
    # Direct edit popup - user can ESC to cancel
    p = Popup(title="SSH Command")
    p.header("Remote Execution")
    p.warning("Command: sudo systemctl restart nginx")

    edited = p.input(
        placeholder="Press Enter to execute or ESC to cancel",
        header="Edit command:",
        value="sudo systemctl restart nginx",
    )

    if edited:
        print(f"Executing: {edited}")
        return edited
    else:
        print("Cancelled by user")
        return None


def input_examples():
    """Various input methods."""
    p = Popup(title="Input Examples")

    # Text input
    name = p.input(placeholder="Enter hostname...", header="SSH Host:", value="localhost")
    print(f"Host: {name}")

    # Password input
    pwd = p.input(placeholder="Enter password...", header="Authentication:", password=True)
    print(f"Password length: {len(pwd)}")

    return name, pwd


def quick_dialogs():
    """Convenience functions for simple dialogs."""

    # Quick confirm
    if quick_confirm("Delete temporary files?"):
        print("Files would be deleted")

    # Quick choice
    action = quick_choice("Build Target", ["development", "staging", "production"])
    print(f"Building for: {action}")

    # Quick input
    branch = quick_input("Enter branch name:")
    print(f"Switching to: {branch}")


def multi_select():
    """Multiple selection example."""
    p = Popup(title="Feature Flags")

    # Note: returns list when limit > 1
    features = p.choose(
        [
            ("monitoring", "Enable Monitoring"),
            ("logging", "Verbose Logging"),
            ("debug", "Debug Mode"),
            ("profiling", "Performance Profiling"),
        ],
        header="Select features to enable:",
        limit=4,  # Allow multiple
        selected_prefix="[x] ",
        unselected_prefix="[ ] ",
    )

    print(f"Enabled: {features}")
    return features


def pager_example():
    """Display scrollable content."""
    p = Popup(title="Log Viewer")

    # Generate some content
    content = "\n".join([f"2024-01-15 10:23:{i:02d} - Log entry {i}" for i in range(50)])

    p.header("System Logs")
    p.info("Use arrows/pgup/pgdn to scroll, q to exit")
    p.pager(content, show_line_numbers=True)

    print("Pager closed")
