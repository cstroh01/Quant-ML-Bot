"""Shared chart setup and saving helpers.

Every script here renders to a file rather than a window, so the matplotlib
backend and the save-and-close sequence are identical in all of them. Keeping
that in one place means a headless environment only has to be handled once.
"""

from pathlib import Path

# Select a non-interactive matplotlib backend before importing pyplot. This
# matters when a script runs on a server or in another headless environment
# where there is no desktop window in which to display a chart.
import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt

# Re-exported so callers reach pyplot only through this module. That is what
# guarantees the backend above is selected first; importing pyplot directly in
# each script would make correctness depend on import order.
__all__ = ["plt", "save_figure"]


def save_figure(figure: plt.Figure, path: Path, dpi: int = 150) -> Path:
    """Lay out, write, and close a figure, then report where it landed."""
    path.parent.mkdir(parents=True, exist_ok=True)
    figure.tight_layout()
    figure.savefig(path, dpi=dpi)
    # Closing matters even in a short script: figures held open by pyplot are
    # never garbage collected, so a loop that forgets this leaks memory.
    plt.close(figure)
    print(f"\nSaved plot to: {path}")
    return path
