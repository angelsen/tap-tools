#!/usr/bin/env python3
"""Combined Canvas + Input examples for tmux-popup.

Demonstrates:
- Display information then get input
- Multi-step workflows
- Help screens with choices
- Forms with instructions
"""

from tmux_popup import Popup, Canvas, Row, Column, Text, Markdown, Input, Choose, Filter, Confirm


def help_and_choice():
    """Display help information then get user choice."""
    popup = Popup(width="75%", height="60%")

    # Canvas with help information
    canvas = Canvas(border="rounded", padding="1")
    canvas.add(
        Markdown("""# Git Operations Help

## Available Commands

**commit** - Save changes to the repository
**push** - Upload commits to remote repository  
**pull** - Download changes from remote repository
**branch** - Create or switch branches
**merge** - Combine branches together

Select an operation to continue.""")
    )

    popup.add(canvas)

    # Choice after displaying help
    operations = {
        "Commit changes": "commit",
        "Push to remote": "push",
        "Pull from remote": "pull",
        "Manage branches": "branch",
        "Merge branches": "merge",
        "Cancel": None,
    }

    result = popup.add(Choose(options=operations, header="Select Git operation:")).show()

    if result:
        print(f"Executing: git {result}")
    else:
        print("Operation cancelled")


def registration_form():
    """Multi-step registration form with instructions."""
    # Step 1: Show instructions
    popup = Popup(width="70%", height="50%")
    canvas = Canvas(border="double", padding="1")
    canvas.add(
        Markdown("""# User Registration

Please provide the following information:
1. Your full name
2. Email address
3. Select your role

Press any key to continue...""")
    )
    popup.add(canvas).show()

    # Step 2: Get name
    popup = Popup(width="60%", height="30%")
    name = popup.add(Input(prompt="Full name: ", placeholder="John Doe", header="Step 1 of 3: Enter your name")).show()

    if not name:
        print("Registration cancelled")
        return

    # Step 3: Get email
    email = popup.add(
        Input(prompt="Email: ", placeholder="user@example.com", header="Step 2 of 3: Enter your email")
    ).show()

    if not email:
        print("Registration cancelled")
        return

    # Step 4: Select role
    role = popup.add(
        Choose(options=["Admin", "User", "Guest", "Developer"], header="Step 3 of 3: Select your role")
    ).show()

    if not role:
        print("Registration cancelled")
        return

    # Step 5: Confirm
    popup = Popup(width="70%", height="40%")
    canvas = Canvas(border="rounded", padding="1")
    canvas.add(
        Markdown(f"""# Confirm Registration

**Name:** {name}
**Email:** {email}
**Role:** {role}

Is this information correct?""")
    )
    popup.add(canvas)

    confirmed = popup.add(
        Confirm(prompt="Proceed with registration?", affirmative="Yes, register", negative="No, cancel")
    ).show()

    if confirmed:
        print(f"✅ User registered: {name} ({email}) as {role}")
    else:
        print("Registration cancelled")


def code_review():
    """Display code for review then get approval."""
    popup = Popup(width="85%", height="65%")

    # Canvas with code review layout
    canvas = Canvas(padding="1")
    canvas.add(Text("Code Review: Feature #123"))
    canvas.add(Text("=" * 50))

    # Two columns: old code vs new code
    left = Column(width="50%", border="normal", padding="1", margin="0 1 0 0")
    left.add(
        Markdown("""### BEFORE:

```python
def calculate(x, y):
    # Old implementation
    result = x + y
    return result
```""")
    )

    right = Column(width="50%", border="normal", padding="1")
    right.add(
        Markdown("""### AFTER:

```python
def calculate(x: float, y: float) -> float:
    \"\"\"Calculate sum with type hints.\"\"\"
    if not isinstance(x, (int, float)):
        raise TypeError("x must be numeric")
    if not isinstance(y, (int, float)):
        raise TypeError("y must be numeric")
    return x + y
```""")
    )

    canvas.add(Row(left, right))
    canvas.add(Text(""))
    canvas.add(Text("Changes: Added type hints and validation"))

    popup.add(canvas)

    # Get review decision
    result = popup.add(
        Choose(options=["Approve", "Request Changes", "Comment", "Reject"], header="Review Decision:")
    ).show()

    print(f"Review decision: {result}")


def package_installer():
    """Show available packages then allow selection."""
    popup = Popup(width="80%", height="70%")

    # Display package information
    canvas = Canvas(border="rounded", padding="1")
    canvas.add(
        Markdown("""# Python Package Installer

## Categories

**Data Science**: numpy, pandas, matplotlib, scikit-learn
**Web Development**: django, flask, fastapi, requests
**Testing**: pytest, tox, coverage, mock
**Linting**: black, ruff, mypy, pylint

Select packages to install using the filter below.""")
    )

    popup.add(canvas)

    # Package selection with categories
    packages = {
        "numpy (Data Science)": "numpy",
        "pandas (Data Science)": "pandas",
        "matplotlib (Plotting)": "matplotlib",
        "scikit-learn (ML)": "scikit-learn",
        "django (Web Framework)": "django",
        "flask (Web Framework)": "flask",
        "fastapi (API Framework)": "fastapi",
        "requests (HTTP Client)": "requests",
        "pytest (Testing)": "pytest",
        "black (Formatter)": "black",
        "ruff (Linter)": "ruff",
        "mypy (Type Checker)": "mypy",
    }

    selected = popup.add(
        Filter(
            options=packages,
            no_limit=True,
            fuzzy=True,
            placeholder="Type to filter packages...",
            header="Select packages (Space to select, Enter to install):",
        )
    ).show()

    if selected:
        print(f"Installing {len(selected)} packages:")
        for pkg in selected:
            print(f"  - {pkg}")
    else:
        print("No packages selected")


def error_details():
    """Show error details then ask for action."""
    popup = Popup(width="75%", height="55%")

    # Display error information
    canvas = Canvas(border="thick", padding="1")
    canvas.add(Markdown("# ⚠️  Error Detected"))
    canvas.add(Text(""))
    canvas.add(
        Markdown("""```python
Traceback (most recent call last):
  File "app.py", line 42, in process_data
    result = calculate_average(numbers)
  File "utils.py", line 15, in calculate_average
    return sum(nums) / len(nums)
ZeroDivisionError: division by zero
```""")
    )
    canvas.add(Text(""))
    canvas.add(
        Markdown("""**Possible causes:**
- Empty list passed to function
- No data validation before calculation
- Missing error handling""")
    )

    popup.add(canvas)

    # Ask for action
    action = popup.add(
        Choose(
            options=[
                "View full stacktrace",
                "Open file in editor",
                "Search for similar issues",
                "Ignore and continue",
                "Exit program",
            ],
            header="How would you like to proceed?",
        )
    ).show()

    print(f"Action: {action}")


def settings_with_preview():
    """Show current settings then allow modification."""
    popup = Popup(width="80%", height="60%")

    # Display current settings
    canvas = Canvas(border="rounded", padding="1")
    canvas.add(Markdown("# Application Settings"))
    canvas.add(Text(""))

    # Two-column layout for settings
    left = Column(width="50%", padding="1")
    left.add(
        Markdown("""## Current Configuration

**Theme:** Dark
**Font Size:** 14px
**Auto-save:** Enabled
**Tab Size:** 4 spaces
**Line Numbers:** Visible""")
    )

    right = Column(width="50%", padding="1")
    right.add(
        Markdown("""## Shortcuts

**Save:** Ctrl+S
**Open:** Ctrl+O
**Find:** Ctrl+F
**Replace:** Ctrl+H
**Settings:** Ctrl+,""")
    )

    canvas.add(Row(left, right))
    popup.add(canvas)

    # Settings menu
    result = popup.add(
        Choose(
            options=[
                "Change Theme",
                "Adjust Font Size",
                "Toggle Auto-save",
                "Configure Tab Size",
                "Reset to Defaults",
                "Save and Close",
            ],
            header="Select setting to modify:",
        )
    ).show()

    print(f"Selected: {result}")


def main():
    """Run all combined examples."""
    examples = [
        ("Help Screen + Choice", help_and_choice),
        ("Multi-step Registration Form", registration_form),
        ("Code Review Interface", code_review),
        ("Package Installer", package_installer),
        ("Error Display + Action", error_details),
        ("Settings with Preview", settings_with_preview),
    ]

    print("tmux-popup Combined Examples (Canvas + Input)")
    print("=" * 50)
    for i, (name, func) in enumerate(examples, 1):
        print(f"{i}. {name}")
    print("0. Exit")
    print()

    while True:
        try:
            choice = input("Select an example (0-6): ")
            idx = int(choice)
            if idx == 0:
                break
            if 1 <= idx <= len(examples):
                examples[idx - 1][1]()
                print()  # Add spacing
            else:
                print("Invalid choice")
        except (ValueError, KeyboardInterrupt):
            break

    print("\nGoodbye!")


if __name__ == "__main__":
    main()
