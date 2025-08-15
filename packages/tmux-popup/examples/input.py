#!/usr/bin/env python3
"""Input-only interactive examples for tmux-popup.

Demonstrates:
- Text input (Input)
- Single selection (Choose)
- Multi-selection (Filter)
- Confirmation (Confirm)
- File picker (FilePicker)
- Table selection (Table)
"""

from tmux_popup import Popup, Input, Choose, Filter, Confirm, FilePicker, Table, Write


def text_input():
    """Simple text input example."""
    popup = Popup(width="60%", height="30%")
    result = popup.add(Input(prompt="Enter your name: ", placeholder="John Doe", header="User Registration")).show()

    if result:
        print(f"Hello, {result}!")
    else:
        print("No input provided")


def single_choice():
    """Single selection from a list."""
    popup = Popup(width="50%", height="40%")

    options = ["Python", "JavaScript", "Go", "Rust", "TypeScript"]

    result = popup.add(Choose(options=options, header="Select your favorite language:")).show()

    if result:
        print(f"You selected: {result}")
    else:
        print("No selection made")


def dict_choice_menu():
    """Menu with label:value pairs using dict."""
    popup = Popup(width="60%", height="50%")

    # Dict options - displays labels, returns values
    actions = {
        "📝 Create New File": "create",
        "📂 Open Existing File": "open",
        "💾 Save Current File": "save",
        "🔍 Search in Files": "search",
        "⚙️  Settings": "settings",
        "❌ Exit": "exit",
    }

    result = popup.add(Choose(options=actions, header="What would you like to do?")).show()

    if result:
        print(f"Action selected: {result}")
    else:
        print("Cancelled")


def multi_select():
    """Multiple selection with fuzzy filtering."""
    popup = Popup(width="70%", height="50%")

    packages = [
        "numpy",
        "pandas",
        "matplotlib",
        "scikit-learn",
        "tensorflow",
        "pytorch",
        "fastapi",
        "django",
        "flask",
        "requests",
        "beautifulsoup4",
        "selenium",
        "pytest",
        "black",
        "ruff",
        "mypy",
    ]

    result = popup.add(
        Filter(
            options=packages,
            no_limit=True,  # Allow multiple selections
            fuzzy=True,  # Enable fuzzy search
            placeholder="Type to filter packages...",
            header="Select packages to install (Space to select, Enter to confirm):",
        )
    ).show()

    if result:
        print(f"Selected {len(result)} packages: {', '.join(result)}")
    else:
        print("No packages selected")


def confirmation():
    """Yes/No confirmation dialog."""
    popup = Popup(width="50%", height="25%")

    result = popup.add(
        Confirm(
            prompt="Are you sure you want to delete all temporary files?",
            affirmative="Yes, delete them",
            negative="No, keep them",
            default=False,
        )
    ).show()

    if result:
        print("Files would be deleted")
    else:
        print("Operation cancelled")


def file_picker():
    """File selection dialog."""
    popup = Popup(width="70%", height="50%")

    result = popup.add(
        FilePicker(
            ".",  # Start in current directory (positional arg)
            all=True,  # Show hidden files
            file=True,  # Allow file selection
            height=15,
        )
    ).show()

    if result:
        print(f"Selected file: {result}")
    else:
        print("No file selected")


def table_selection():
    """Select from tabular data."""
    popup = Popup(width="70%", height="40%")

    # Table data as list of dicts
    users = [
        {"Name": "Alice", "Role": "Admin", "Status": "Active", "Last Login": "Today"},
        {"Name": "Bob", "Role": "User", "Status": "Active", "Last Login": "Yesterday"},
        {"Name": "Charlie", "Role": "Guest", "Status": "Inactive", "Last Login": "1 week ago"},
        {"Name": "Diana", "Role": "User", "Status": "Active", "Last Login": "Today"},
        {"Name": "Eve", "Role": "Admin", "Status": "Active", "Last Login": "2 days ago"},
    ]

    # Note: Don't pass 'header' to Table - it's not supported for interactive mode
    result = popup.add(Table(data=users, border="rounded")).show()

    if result:
        print(f"Selected user: {result}")
    else:
        print("No user selected")


def multi_line_input():
    """Multi-line text editor."""
    popup = Popup(width="70%", height="50%")

    result = popup.add(
        Write(
            placeholder="Enter your message here...\n\nSupports multiple lines.",
            header="Compose Message",
            width=60,
            height=10,
        )
    ).show()

    if result:
        print("Message received:")
        print("-" * 40)
        print(result)
        print("-" * 40)
    else:
        print("No message entered")


def main():
    """Run all input examples."""
    examples = [
        ("Text Input", text_input),
        ("Single Choice", single_choice),
        ("Menu (Dict Options)", dict_choice_menu),
        ("Multi-Select Filter", multi_select),
        ("Confirmation Dialog", confirmation),
        ("File Picker", file_picker),
        ("Table Selection", table_selection),
        ("Multi-line Editor", multi_line_input),
    ]

    print("tmux-popup Input Examples")
    print("=" * 40)
    for i, (name, func) in enumerate(examples, 1):
        print(f"{i}. {name}")
    print("0. Exit")
    print()

    while True:
        try:
            choice = input("Select an example (0-8): ")
            idx = int(choice)
            if idx == 0:
                break
            if 1 <= idx <= len(examples):
                examples[idx - 1][1]()
                print()  # Add spacing between examples
            else:
                print("Invalid choice")
        except (ValueError, KeyboardInterrupt):
            break

    print("\nGoodbye!")


if __name__ == "__main__":
    main()
