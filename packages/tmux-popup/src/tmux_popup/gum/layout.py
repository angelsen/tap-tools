"""Layout commands for gum (join)."""

from typing import List
from .base import _DisplayCommand


class GumJoin(_DisplayCommand):
    """Join text vertically or horizontally."""

    def __init__(
        self,
        texts: List[str],
        horizontal: bool = False,
        align: str = "left",  # left, center, right
    ):
        """Initialize join command.

        Args:
            texts: List of text strings to join.
            horizontal: Join horizontally (default is vertical).
            align: Text alignment.
        """
        super().__init__("join")
        self.texts = texts
        self.horizontal = horizontal
        self.align = align

    def render(self) -> List[str]:
        """Render join command."""
        args = self.build_base_cmd()

        # Join-specific args
        if self.horizontal:
            args.append("--horizontal")
        else:
            args.append("--vertical")

        if self.align != "left":
            args.extend(["--align", self.align])

        # Add texts
        for text in self.texts:
            args.append(self.quote(text))

        return [" ".join(args)]
