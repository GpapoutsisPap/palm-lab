"""Typed failures for action execution."""


class ActionError(Exception):
    """Base class for anything that can go wrong running an action."""

    def user_message(self) -> str:
        """A short description suitable for a notification."""
        return str(self)


class AppNotFoundError(ActionError):
    """A launch target could not be resolved to an executable."""

    def __init__(self, target: str) -> None:
        super().__init__(f"Could not find an application named {target!r}")
        self.target = target

    def user_message(self) -> str:
        return f"{self.target} isn't installed, or palm-lab can't find it"


class LaunchFailedError(ActionError):
    """The executable was found but would not start."""

    def __init__(self, target: str, reason: str) -> None:
        super().__init__(f"Failed to launch {target!r}: {reason}")
        self.target = target
        self.reason = reason


class InvalidBindingError(ActionError):
    """The configuration file could not be understood."""
