from enum import Enum
from typing import List, final

from pydantic import BaseModel

from cjdev.shared.context import CjDevContext
from cjdev.shared.proc import Process


@final
class BuildType(Enum):
    DEBUG = "debug"
    RELEASE = "release"
    RELEASE_WITH_DEBUG_INFO = "relwithdebinfo"


@final
class BuildContext(BaseModel):
    global_ctx: CjDevContext
    build_type: BuildType

    def make_common_build_args(self) -> List[str]:
        return [*self._make_common_args(), "build", "-t", self.build_type.value]

    def make_common_install_args(self) -> List[str]:
        return [*self._make_common_args(), "install"]

    def make_common_clean_args(self) -> List[str]:
        return [*self._make_common_args(), "clean"]

    def _make_common_args(self) -> List[str]:
        return ["python3", "build.py"]
