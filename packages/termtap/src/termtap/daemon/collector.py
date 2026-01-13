"""Collector script for tmux pipe-pane.

Usage: python -m termtap.daemon.collector <pane_id>
"""

import os
import socket
import sys

from ..paths import COLLECTOR_SOCK_PATH


def main():
    if len(sys.argv) != 2:
        sys.exit(1)

    pane_id = sys.argv[1]
    fd = sys.stdin.fileno()

    try:
        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as sock:
            sock.connect(str(COLLECTOR_SOCK_PATH))
            sock.sendall(f"{pane_id}\n".encode())
            while chunk := os.read(fd, 4096):
                sock.sendall(chunk)
    except (ConnectionRefusedError, BrokenPipeError, OSError) as e:
        print(f"collector[{pane_id}]: socket error: {e}", file=sys.stderr)
    except Exception as e:
        print(f"collector[{pane_id}]: unexpected error: {e}", file=sys.stderr)
        raise


if __name__ == "__main__":
    main()
