#!/usr/bin/env python3
"""Canvas-only display examples for tmux-popup.

Demonstrates:
- Text and Markdown content
- Layout with Row and Column
- Styling with borders and padding
"""

from tmux_popup import Popup, Canvas, Row, Column, Text, Markdown


def hello_world():
    """Simple hello world popup."""
    popup = Popup(width="50%", height="20%")
    canvas = Canvas(border="rounded", padding="1")
    canvas.add(Text("Hello, tmux-popup!"))
    canvas.add(Text(""))
    canvas.add(Text("Press any key to close..."))
    popup.add(canvas).show()


def markdown_showcase():
    """Showcase markdown formatting capabilities."""
    popup = Popup(width="70%", height="50%")
    canvas = Canvas(border="double", padding="1")

    markdown_content = """# tmux-popup Features

## Formatting Support
- **Bold text** and *italic text*
- `Inline code` snippets
- [Links](https://github.com) (displayed as text)

### Lists
1. Numbered lists
2. With multiple items
   - Nested bullets
   - Work great

### Code Blocks
```python
def greet(name):
    return f"Hello, {name}!"
```

> Blockquotes for important notes
"""

    canvas.add(Markdown(markdown_content))
    popup.add(canvas).show()


def code_examples():
    """Show code examples in different languages."""
    popup = Popup(width="80%", height="60%")
    canvas = Canvas(border="rounded", padding="1")

    canvas.add(
        Markdown("""# Code Examples

## Python

```python
def fibonacci(n):
    if n <= 1:
        return n
    return fibonacci(n-1) + fibonacci(n-2)
```

## JavaScript

```javascript
const greet = (name) => {
    console.log(`Hello, ${name}!`);
};
```
""")
    )

    popup.add(canvas).show()


def two_column_layout():
    """Display content in a two-column layout."""
    popup = Popup(width="85%", height="55%")
    canvas = Canvas(padding="1")

    # Left column - Documentation
    left = Column(width="50%", border="normal", padding="1", margin="0 1 0 0")
    left.add(Markdown("## Documentation\n\nThis is the **left column** with markdown content."))
    left.add(Text(""))
    left.add(Text("Features:"))
    left.add(Text("• Automatic width calculation"))
    left.add(Text("• Border and padding support"))
    left.add(Text("• Flexible content types"))

    # Right column - Code
    right = Column(width="50%", border="normal", padding="1")
    right.add(
        Markdown("""## Example Code

```python
from tmux_popup import Popup, Canvas

popup = Popup()
canvas = Canvas()
canvas.add("Hello!")
popup.add(canvas).show()
```""")
    )

    canvas.add(Row(left, right))
    popup.add(canvas).show()


def centered_content():
    """Display centered content with styling."""
    popup = Popup(width="70%", height="40%")

    # Outer canvas takes full popup space
    canvas = Canvas(width="100%", height="100%", align="center")

    # Inner content with border, centered
    inner = Column(width="60%", border="thick", padding="2", align="center")
    inner.add(Markdown("# 🎉 Success!"))
    inner.add(Text(""))
    inner.add(Text("Your operation completed successfully."))
    inner.add(Text(""))
    inner.add(Text("This content is centered both"))
    inner.add(Text("horizontally and vertically."))

    canvas.add(inner)
    popup.add(canvas).show()


def main():
    """Run all display examples."""
    examples = [
        ("Hello World", hello_world),
        ("Markdown Showcase", markdown_showcase),
        ("Code Examples", code_examples),
        ("Two-Column Layout", two_column_layout),
        ("Centered Content", centered_content),
    ]

    print("tmux-popup Display Examples")
    print("=" * 40)
    for i, (name, func) in enumerate(examples, 1):
        print(f"{i}. {name}")
    print("0. Exit")
    print()

    while True:
        try:
            choice = input("Select an example (0-5): ")
            idx = int(choice)
            if idx == 0:
                break
            if 1 <= idx <= len(examples):
                examples[idx - 1][1]()
            else:
                print("Invalid choice")
        except (ValueError, KeyboardInterrupt):
            break

    print("\nGoodbye!")


if __name__ == "__main__":
    main()
