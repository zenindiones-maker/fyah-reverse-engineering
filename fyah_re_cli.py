"""Entry point for the Fyah Reverse Engineering command-line interface."""

from __future__ import annotations

import sys
from typing import Sequence

from tools.__main__ import main as tools_main


def main(argv: Sequence[str] | None = None) -> int:
    """Run the shared tools CLI; preserve argparse's non-zero error behavior."""
    return tools_main(list(argv) if argv is not None else None)


if __name__ == "__main__":
    sys.exit(main())
