#!/usr/bin/env python3
"""
tmux-popup Demo - Interactive showcase of all components

Run this demo to see tmux-popup capabilities:
    python demo.py
"""

from tmux_popup import Popup
from tmux_popup.gum import (
    GumStyle, GumInput, GumConfirm, GumChoose, 
    GumFilter, GumTable, GumWrite, GumPager
)


def main():
    """Main demo flow."""
    
    # Welcome screen
    popup = Popup(width="70", title="tmux-popup Demo")
    popup.add(
        GumStyle("🎉 Welcome to tmux-popup!", header=True),
        "",
        "This demo will showcase the different components available.",
        "Press Enter to continue..."
    ).show()
    
    # Get user info
    popup = Popup(width="60", title="User Setup")
    name = popup.add(
        GumStyle("Let's get to know you", header=True),
        "",
        "What's your name?",
        GumInput(placeholder="Enter your name...", value="")
    ).show()
    
    if not name:
        print("Demo cancelled")
        return
    
    # Choose demo section
    popup = Popup(width="65", title="Demo Sections")
    section = popup.add(
        GumStyle(f"Hello, {name}!", info=True),
        "",
        "Which demo would you like to see?",
        "",
        GumChoose([
            ("input", "📝 Input Components"),
            ("select", "🎯 Selection Components"),
            ("display", "🎨 Display Components"),
            ("workflow", "🔄 Complete Workflow"),
            ("all", "✨ All Demos"),
            ("quit", "❌ Exit Demo")
        ])
    ).show()
    
    if section == "quit" or not section:
        print("Thanks for trying tmux-popup!")
        return
    
    if section in ["input", "all"]:
        demo_input()
    
    if section in ["select", "all"]:
        demo_selection()
    
    if section in ["display", "all"]:
        demo_display()
    
    if section in ["workflow", "all"]:
        demo_workflow()
    
    # Goodbye
    popup = Popup(width="60")
    popup.add(
        GumStyle("✅ Demo Complete!", header=True),
        "",
        f"Thanks for trying tmux-popup, {name}!",
        "",
        "Install: uv add tmux-popup (or pip install tmux-popup)",
        "GitHub: https://github.com/angelsen/tap-tools"
    ).show()


def demo_input():
    """Demonstrate input components."""
    popup = Popup(width="65", title="Input Demo")
    
    # Single line input
    email = popup.add(
        GumStyle("📧 Email Input", header=True),
        "",
        "Enter your email address:",
        GumInput(placeholder="user@example.com", value="")
    ).show()
    
    if email:
        print(f"Email captured: {email}")
    
    # Multi-line input
    popup = Popup(width="70", height="20", title="Text Editor")
    notes = popup.add(
        GumStyle("📝 Multi-line Text Editor", header=True),
        "",
        "Write some notes (Ctrl+D to save, Esc to cancel):",
        "",
        GumWrite(placeholder="Start typing...", value="# My Notes\n\n")
    ).show()
    
    if notes:
        print(f"Notes captured ({len(notes)} chars)")
    
    # Confirmation
    popup = Popup(width="60")
    confirmed = popup.add(
        GumStyle("⚠️ Confirmation", warning=True),
        "",
        "This is a confirmation dialog.",
        "Would you like to proceed?",
        "",
        GumConfirm("Continue with demo?", default=True)
    ).show()
    
    print(f"Confirmed: {confirmed}")


def demo_selection():
    """Demonstrate selection components."""
    
    # Single choice
    popup = Popup(width="60", title="Single Selection")
    language = popup.add(
        GumStyle("🔤 Choose Your Favorite Language", header=True),
        "",
        GumChoose([
            ("python", "🐍 Python"),
            ("javascript", "📜 JavaScript"),
            ("go", "🐹 Go"),
            ("rust", "🦀 Rust"),
            ("typescript", "📘 TypeScript")
        ])
    ).show()
    
    if language:
        print(f"Selected language: {language}")
    
    # Multiple selection with filter
    popup = Popup(width="65", height="15", title="Multi-Select")
    frameworks = [
        "Django", "Flask", "FastAPI", "React", "Vue", 
        "Angular", "Svelte", "Express", "Next.js", "Nuxt.js"
    ]
    
    selected = popup.add(
        GumStyle("🛠️ Select Frameworks You Know", info=True),
        "",
        "Use Tab to select, Enter to confirm:",
        "",
        GumFilter(frameworks, limit=0, fuzzy=True, placeholder="Search...")
    ).show()
    
    if selected:
        print(f"Selected {len(selected)} frameworks: {', '.join(selected)}")
    
    # Table selection
    popup = Popup(width="70", title="Table Selection")
    servers = [
        ["🟢", "prod-01", "192.168.1.10", "8 GB", "Running"],
        ["🟡", "dev-01", "192.168.1.20", "4 GB", "Idle"],
        ["🟢", "prod-02", "192.168.1.11", "8 GB", "Running"],
        ["🔴", "test-01", "192.168.1.30", "2 GB", "Stopped"],
    ]
    
    selected_server = popup.add(
        GumStyle("🖥️ Select a Server", header=True),
        "",
        GumTable(
            servers,
            headers=["Status", "Name", "IP", "RAM", "State"],
            return_column=1  # Return the name column
        )
    ).show()
    
    if selected_server:
        print(f"Selected server: {selected_server}")


def demo_display():
    """Demonstrate display components."""
    
    # Styled text variations
    popup = Popup(width="65", title="Styled Text")
    popup.add(
        GumStyle("🎨 Text Styling Options", header=True),
        "",
        GumStyle("ℹ️ This is an info message", info=True),
        GumStyle("⚠️ This is a warning", warning=True),
        GumStyle("❌ This is an error", error=True),
        "",
        "Press Enter to continue..."
    ).show()
    
    # Pager for long content
    popup = Popup(width="70", height="20", title="Pager Demo")
    long_text = """# tmux-popup Documentation

## Overview
tmux-popup is a composable popup system for tmux that provides
rich terminal UI components through the gum library.

## Features
- Rich component library
- Composable API
- Zero Python dependencies
- Type-safe results
- Easy to use

## Components

### Input Components
- GumInput: Single-line text input
- GumWrite: Multi-line text editor
- GumConfirm: Yes/no confirmation

### Selection Components
- GumChoose: Single selection from list
- GumFilter: Fuzzy search with multi-select
- GumTable: Table with row selection

### Display Components
- GumStyle: Styled text output
- GumPager: Scrollable text viewer
- GumFormat: Template formatting

## Installation
pip install tmux-popup

## Quick Start
from tmux_popup import Popup
from tmux_popup.gum import GumStyle, GumInput

popup = Popup()
result = popup.add(
    GumStyle("Hello!", header=True),
    GumInput()
).show()
"""
    
    popup.add(
        GumStyle("📚 Documentation Viewer", header=True),
        "",
        "Use arrow keys to scroll, q to exit:",
        "",
        GumPager(long_text)
    ).show()


def demo_workflow():
    """Demonstrate a complete workflow."""
    
    # Git-like workflow
    popup = Popup(width="65", title="Git Workflow")
    
    # Step 1: Choose action
    action = popup.add(
        GumStyle("🔀 Git Actions", header=True),
        "",
        "What would you like to do?",
        "",
        GumChoose([
            ("commit", "💾 Create a commit"),
            ("branch", "🌿 Switch branch"),
            ("push", "📤 Push changes"),
            ("pull", "📥 Pull changes"),
            ("status", "📊 Check status")
        ])
    ).show()
    
    if not action:
        return
    
    print(f"Selected action: {action}")
    
    if action == "commit":
        # Step 2: Get commit message
        popup = Popup(width="70", height="15", title="Commit Message")
        message = popup.add(
            GumStyle("✍️ Write Commit Message", header=True),
            "",
            GumWrite(
                placeholder="Enter commit message...",
                value="feat: "
            )
        ).show()
        
        if message:
            # Step 3: Confirm
            popup = Popup(width="65")
            confirmed = popup.add(
                GumStyle("📝 Review Commit", info=True),
                "",
                f"Message: {message.split()[0]}...",
                "",
                GumConfirm("Create this commit?", default=True)
            ).show()
            
            if confirmed:
                print(f"Would execute: git commit -m '{message}'")
    
    elif action == "branch":
        # Show branch selector
        branches = ["main", "develop", "feature/popup", "bugfix/issue-42"]
        popup = Popup(width="60", title="Branch Selection")
        branch = popup.add(
            GumStyle("🌿 Select Branch", header=True),
            "",
            GumFilter(branches, fuzzy=True, placeholder="Search branches...")
        ).show()
        
        if branch and len(branch) > 0:
            print(f"Would execute: git checkout {branch[0]}")


if __name__ == "__main__":
    main()