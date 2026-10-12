"""What cjdev remembers about a branch set, as opposed to what git can tell it.

`state.py` is read back from git every time; this is the part git has no
answer for. One record per branch set, so every later command reads its
context from here instead of being told again.
"""

import re
from dataclasses import dataclass
from typing import final

from cjdev.domain.build import Profile

SLUG_LENGTH = 40
"""Of the title's part of a derived name: enough to recognise the issue in
`ls`, short enough that a path under it stays readable."""


@final
@dataclass(frozen=True)
class Task:
    """What the branch set is for: the issue, and the project it lives in.

    `issue` is None for a task started without one, until one is attached.
    `home` is written by every command that writes a task; None only in a
    record written by hand, and read as `[forge] issue_home`.
    """

    home: str | None
    issue: str | None = None


def task_name(number: str, title: str) -> str:
    """`issue-<n>-<slug>`. A title with nothing ASCII in it, which upstream
    issues often are, leaves `issue-<n>`."""
    slug = re.sub(r"[^a-z0-9]+", "-", title.lower()).strip("-")
    if len(slug) > SLUG_LENGTH:
        slug = slug[:SLUG_LENGTH].rsplit("-", 1)[0]
    return f"issue-{number}-{slug}" if slug else f"issue-{number}"


@final
@dataclass(frozen=True)
class BranchSetRecord:
    profile: Profile | None = None
    """The profile of the last full build. None until there has been one,
    which is not the same as release: nothing has been built yet to agree
    with."""
    task: Task | None = None
    """None for a branch set nobody started as a task: `branch new` records
    nothing."""

    def default_profile(self) -> Profile:
        return self.profile or Profile.RELEASE
