"""Target resolution - handles all target to pane resolution logic.

PUBLIC API:
  - resolve_targets_to_panes: Resolve one or more targets to list of panes
  - resolve_target_to_pane: Resolve target to single pane (backwards compat)
  - resolve_or_create_target: Resolve or create target session/pane
"""

from typing import List, Tuple, Union
from .core import run_tmux, _get_pane_id
from .pane import list_panes
from ._exceptions import PaneNotFoundError
from ..types import Target, SessionWindowPane, _classify_target, _parse_convenience_target


def _resolve_target_to_panes(target: Target) -> List[Tuple[str, SessionWindowPane]]:
    """Resolve single target to list of panes.

    Args:
        target: Target identifier.
    """
    target_type, value = _classify_target(target)

    if target_type == "pane_id":
        code, stdout, _ = run_tmux(["list-panes", "-t", value, "-F", "#{session_name}:#{window_index}.#{pane_index}"])
        swp = stdout.strip()
        return [(value, swp)]

    elif target_type == "swp":
        parts = value.split(":")
        session = parts[0]

        if len(parts) > 1 and "." in parts[1]:
            # session:window.pane
            window_pane = parts[1].split(".")
            window = window_pane[0]
            pane = window_pane[1]
            pane_id = _get_pane_id(session, window, pane)
            if pane_id is None:
                raise PaneNotFoundError(f"Pane not found: {session}:{window}.{pane}")
            return [(pane_id, value)]
        elif len(parts) > 1:
            # session:window
            window = parts[1]
            panes = list_panes(all=False, window=f"{session}:{window}")
            return [(p.pane_id, p.swp) for p in panes]
        else:
            # Just session
            panes = list_panes(all=False, session=session)
            return [(p.pane_id, p.swp) for p in panes]

    elif target_type == "service":
        from ..config import resolve_service_target

        resolved_swp = resolve_service_target(value)
        if resolved_swp is None:
            raise RuntimeError(f"Service not found: {value}")
        return _resolve_target_to_panes(resolved_swp)

    else:  # convenience
        session, window, pane = _parse_convenience_target(value)

        if pane is not None:
            # "session:window.pane" parsed as convenience
            pane_id = _get_pane_id(session, str(window or 0), str(pane))
            if pane_id is None:
                raise PaneNotFoundError(f"Pane not found: {session}:{window or 0}.{pane}")
            swp = f"{session}:{window or 0}.{pane}"
            return [(pane_id, swp)]
        elif window is not None:
            panes = list_panes(all=False, window=f"{session}:{window}")
            return [(p.pane_id, p.swp) for p in panes]
        else:
            panes = list_panes(all=False, session=session)
            return [(p.pane_id, p.swp) for p in panes]


def resolve_targets_to_panes(targets: Union[Target, List[Target]]) -> List[Tuple[str, SessionWindowPane]]:
    """Resolve one or more targets to list of panes.

    Accepts single target string or list of targets.
    Each target can resolve to multiple panes (e.g., session -> all panes).

    Args:
        targets: Single target or list of target strings.

    Returns:
        List of (pane_id, session_window_pane) tuples.
        Empty list if no panes found.

    Raises:
        RuntimeError: If any target cannot be resolved.
    """
    if isinstance(targets, str):
        targets = [targets]

    all_panes = []
    seen = set()

    for target in targets:
        try:
            panes = _resolve_target_to_panes(target)
            for pane_id, swp in panes:
                if pane_id not in seen:
                    seen.add(pane_id)
                    all_panes.append((pane_id, swp))
        except (RuntimeError, PaneNotFoundError) as e:
            # Add context about which target failed
            raise RuntimeError(f"Failed to resolve target '{target}': {e}")

    return all_panes


def resolve_target_to_pane(target: Target) -> tuple[str, SessionWindowPane]:
    """Resolve target to exactly one pane (backwards compatibility).

    Adds defaults to ensure single pane resolution.
    For targets that could resolve to multiple panes (session, window),
    selects the first pane (adds .0).

    Args:
        target: Any target string.

    Returns:
        Tuple of (pane_id, session_window_pane).

    Raises:
        RuntimeError: If target cannot be resolved.
    """
    target_type, value = _classify_target(target)

    # Service targets always resolve to single pane
    if target_type == "service":
        from ..config import resolve_service_target

        resolved_swp = resolve_service_target(value)
        if not resolved_swp:
            raise RuntimeError(f"Service not found: {value}")
        return resolve_target_to_pane(resolved_swp)

    # For non-service targets, add defaults to get single pane
    if target_type == "convenience":
        session, window, pane = _parse_convenience_target(value)
        # Add defaults
        window = window or 0
        pane = pane or 0
        target = f"{session}:{window}.{pane}"
    elif target_type == "swp" and "." not in value.split(":")[-1]:
        # session:window -> session:window.0
        target = f"{value}.0"

    # Now resolve to single pane
    panes = _resolve_target_to_panes(target)
    if not panes:
        raise RuntimeError(f"Target not found: {target}")

    return panes[0]


def resolve_or_create_target(target: Target, start_dir: str = ".") -> tuple[str, SessionWindowPane]:
    """Resolve target to pane, creating session/window/pane as needed.

    For unambiguous targets only - errors if target resolves to multiple panes.

    Args:
        target: Any target string.
        start_dir: Directory to start in when creating new sessions. Defaults to '.'.

    Returns:
        Tuple of (pane_id, session_window_pane).

    Raises:
        RuntimeError: If target is ambiguous or creation fails.
    """
    # First try to resolve existing
    try:
        panes = _resolve_target_to_panes(target)
    except RuntimeError:
        # Target doesn't exist, proceed to creation
        pass
    else:
        # Target exists - check if unambiguous
        if len(panes) == 1:
            return panes[0]
        elif len(panes) > 1:
            raise RuntimeError(f"Target '{target}' matches {len(panes)} panes - too ambiguous for creation")

    target_type, value = _classify_target(target)

    if target_type == "pane_id":
        raise PaneNotFoundError(f"Pane {value} does not exist")

    elif target_type == "service":
        raise RuntimeError(f"Service {value} not found - use init to create services")

    if target_type == "swp":
        parts = value.split(":")
        session = parts[0]
        if len(parts) > 1 and "." in parts[1]:
            window_pane = parts[1].split(".")
            window = int(window_pane[0])
            pane = int(window_pane[1])
        else:
            window = 0
            pane = 0
    else:  # convenience
        session, window, pane = _parse_convenience_target(value)
        window = window or 0
        pane = pane or 0

    from ._structure import _get_or_create_session_with_structure

    return _get_or_create_session_with_structure(session, window, pane, start_dir)
