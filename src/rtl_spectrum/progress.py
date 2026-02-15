"""Progress reporting utilities.

This module provides thin wrappers for progress feedback, used
by the CLI and long-running operations.
"""

from typing import Callable, Optional


class ProgressReporter:
    """Simple progress reporter with callback support.

    Attributes:
        message: Current status message.
        progress: Current progress as a float between 0.0 and 1.0.
    """

    def __init__(
        self,
        callback: Optional[Callable[[str, float], None]] = None,
    ) -> None:
        """Initialize the progress reporter.

        Args:
            callback: Optional callable receiving ``(message, progress)``
                on each update.
        """
        self.message: str = ""
        self.progress: float = 0.0
        self._callback = callback

    def update(self, message: str, progress: float = 0.0) -> None:
        """Update progress status.

        Args:
            message: Status message to display.
            progress: Progress value between 0.0 and 1.0.
        """
        self.message = message
        self.progress = progress
        if self._callback:
            self._callback(message, progress)
