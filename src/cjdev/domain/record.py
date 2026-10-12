"""What cjdev remembers about a branch set, as opposed to what git can tell it.

`state.py` is read back from git every time; this is the part git has no
answer for. One record per branch set, so every later command reads its
context from here instead of being told again.
"""

from dataclasses import dataclass
from typing import final

from cjdev.domain.build import Profile


@final
@dataclass(frozen=True)
class BranchSetRecord:
    profile: Profile | None = None
    """The profile of the last full build. None until there has been one,
    which is not the same as release: nothing has been built yet to agree
    with."""

    def default_profile(self) -> Profile:
        return self.profile or Profile.RELEASE
