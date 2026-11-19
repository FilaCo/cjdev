"""Branch-set selections layer individual fields over a unit's declared sources."""

from collections.abc import Mapping
from dataclasses import dataclass, replace

from cjdev.domain.manifest import ThirdParty


@dataclass(frozen=True)
class Selection:
    ref: str
    upstream: str | None = None


Selections = Mapping[tuple[str, str], Selection]


def effective(unit: str, source: ThirdParty, choices: Selections) -> ThirdParty:
    choice = choices.get((unit, source.name))
    if choice is None:
        return source
    return replace(source, ref=choice.ref, upstream=choice.upstream or source.upstream)
