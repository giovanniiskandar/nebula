"""Delivering a notification banner on macOS.

Shelling out to `osascript` keeps this dependency-free and needs no signing,
at the cost of the banner being attributed to "Script Editor" rather than
Nebula (PRD §27). Native attribution needs pyobjc and a signed app (§24).
"""

from __future__ import annotations

import logging
import subprocess

logger = logging.getLogger(__name__)

TIMEOUT_SECONDS = 5

# A fixed template. The title and message arrive as arguments, so an allocation
# named `" & (do shell script "...") & "` is text rather than code.
_SCRIPT = """
on run argv
  display notification (item 2 of argv) with title (item 1 of argv)
end run
"""


def build_command(title: str, message: str) -> list[str]:
    """The argv `osascript` is invoked with.

    `-` means "read the script from stdin", so the script is NOT an argument
    here -- it is piped in by `send`. Everything after `-` becomes the script's
    own `argv`, which is what keeps the message out of the script text.
    """
    return ["osascript", "-", title, message]


def send(title: str, message: str) -> bool:
    """Show a banner. Returns whether it was delivered.

    Never raises. Notifying is a side effect of a bridge call that also returns
    the dashboard, so a failure here must not cost the user their tracking
    state -- it is logged and swallowed.
    """
    try:
        result = subprocess.run(
            build_command(title, message),
            # The script arrives on stdin because argv[0] is `-`. Passing it as
            # an argument instead leaves osascript waiting on stdin forever.
            input=_SCRIPT,
            text=True,
            capture_output=True,
            timeout=TIMEOUT_SECONDS,
            check=False,
        )
    except (OSError, subprocess.SubprocessError) as error:
        logger.warning("Could not show a notification: %s", error)
        return False

    if result.returncode != 0:
        logger.warning("osascript exited %s", result.returncode)
        return False
    return True
