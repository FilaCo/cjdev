"""What the machine a build runs on contributes.

Read here rather than where it is used, so that the decision a build makes is
assertable without a particular core count, PATH or ccache on the box.
"""

import multiprocessing
import os
import platform
import shutil
from pathlib import PurePath

from cjdev.domain.build import Host, native_target

LIBRARY_VARS = {"Darwin": "DYLD_FALLBACK_LIBRARY_PATH"}
"""What the SDK's own `envsetup.sh` exports per platform, where it is not
`LD_LIBRARY_PATH`. macOS ignores `DYLD_LIBRARY_PATH` for a hardened process,
which is why the SDK uses the fallback variable and so do we."""


def detect_host() -> Host:
    system, machine = platform.system(), platform.machine()
    library_var = LIBRARY_VARS.get(system, "LD_LIBRARY_PATH")
    return Host(
        target=native_target(system, machine),
        # The whole machine, because units never overlap: the upstream scripts
        # each default to `cpu_count() + 2` when left alone, and two of those
        # nested inside one another is how a build runs out of memory during an
        # LLVM link.
        jobs=multiprocessing.cpu_count(),
        path=os.environ.get("PATH", ""),
        library_var=library_var,
        library_path=os.environ.get(library_var, ""),
        ccache=_which("ccache"),
    )


def _which(program: str) -> PurePath | None:
    found = shutil.which(program)
    return None if found is None else PurePath(found)
