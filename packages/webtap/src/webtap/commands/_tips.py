"""Parser for TIPS.md documentation.

This module reads TIPS.md and provides:
- MCP descriptions for commands
- Developer tips for command responses
- Pre-imported libraries documentation
"""

import re
from pathlib import Path
from typing import Dict, List, Optional


class TipsParser:
    """Parse TIPS.md for command documentation."""

    def __init__(self):
        # TIPS.md is in the same directory as this file
        self.tips_path = Path(__file__).parent / "TIPS.md"
        self.content = self.tips_path.read_text() if self.tips_path.exists() else ""
        self._cache = {}

    def _get_libraries(self) -> str:
        """Extract the libraries section."""
        if "libraries" not in self._cache:
            match = re.search(r"## Libraries\n(.*?)(?=\n##)", self.content, re.DOTALL)
            self._cache["libraries"] = match.group(1).strip() if match else ""
        return self._cache["libraries"]

    def _get_command_section(self, command: str) -> Optional[str]:
        """Get the full section for a command."""
        # Simple and explicit - look for the exact command name
        # Use negative lookahead to ensure we match ### but not ####
        pattern = rf"### {re.escape(command)}\n(.*?)(?=\n###(?!#)|\Z)"
        match = re.search(pattern, self.content, re.DOTALL)
        return match.group(1).strip() if match else None

    def _get_description(self, command: str) -> Optional[str]:
        """Get command description (text before #### sections)."""
        section = self._get_command_section(command)
        if not section:
            return None

        # Extract text before first #### heading
        match = re.match(r"(.*?)(?=\n####|\Z)", section, re.DOTALL)
        return match.group(1).strip() if match else ""

    def _get_examples(self, command: str) -> Optional[str]:
        """Get examples section for a command."""
        section = self._get_command_section(command)
        if not section:
            return None

        # Extract Examples section
        match = re.search(r"#### Examples\n```python\n(.*?)\n```", section, re.DOTALL)
        return match.group(1).strip() if match else None

    def _get_tips(self, command: str, context: Optional[Dict] = None) -> Optional[List[str]]:
        """Get tips list for a command."""
        section = self._get_command_section(command)
        if not section:
            return None

        # Extract Tips section
        match = re.search(r"#### Tips\n(.*?)(?=\n###|\n##|\Z)", section, re.DOTALL)
        if not match:
            return None

        tips_text = match.group(1)
        # Parse bullet points
        tips = re.findall(r"^- (.+)$", tips_text, re.MULTILINE)

        # Apply context substitutions
        if context and tips:
            formatted_tips = []
            for tip in tips:
                for key, value in context.items():
                    tip = tip.replace(f"{{{key}}}", str(value))
                formatted_tips.append(tip)
            return formatted_tips

        return tips

    def _get_mcp_description(self, command: str) -> Optional[str]:
        """Build MCP description from markdown."""
        description = self._get_description(command)
        if not description:
            return None

        # Build complete MCP description
        parts = [description]

        # Add libraries section for certain commands
        if command in ["body", "inspect"]:
            parts.append("")
            parts.append(self._get_libraries())

        # Add examples if available
        examples = self._get_examples(command)
        if examples:
            parts.append("")
            parts.append("Examples:")
            # Indent examples
            for line in examples.split("\n"):
                parts.append(f"  {line}" if line else "")

        return "\n".join(parts)


# Global parser instance
parser = TipsParser()


# Public API
def get_mcp_description(command: str) -> Optional[str]:
    """Get MCP description for a command from TIPS.md.

    Args:
        command: Name of the command.
    """
    return parser._get_mcp_description(command)


def get_tips(command: str, context: Optional[Dict] = None) -> Optional[List[str]]:
    """Get developer tips for a command from TIPS.md.

    Args:
        command: Name of the command.
        context: Optional context for variable substitution.
    """
    return parser._get_tips(command, context)


def get_all_tips() -> Dict[str, List[str]]:
    """Get all available tips from TIPS.md."""
    all_tips = {}

    # Find all command sections
    pattern = r"### ([^\n]+)\n"
    matches = re.findall(pattern, parser.content)

    for command in matches:
        tips = parser._get_tips(command)
        if tips:
            all_tips[command] = tips

    return all_tips
