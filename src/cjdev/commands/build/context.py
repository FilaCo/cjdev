from enum import Enum
from cjdev.shared.context import CjDevContext
from typing import final, List
from pydantic import BaseModel


@final
class BuildType(Enum):
    DEBUG = "debug"
    RELEASE = "release"
    RELEASE_WITH_DEBUG_INFO = "relwithdebinfo"


@final
class BuildContext(BaseModel):
    global_ctx: CjDevContext
    build_type: BuildType

    def get_build_cjc_args() -> List[str]:
        return []
