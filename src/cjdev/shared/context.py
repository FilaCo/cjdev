from pathlib import Path
from cjdev.shared.config import CjDevConfig
from pydantic import BaseModel
from typing import final

_CJDEV_HOME_DIR_NAME = ".cjdev"


@final
class CjDevContext(BaseModel):
    verbose: bool = False
    cfg: CjDevConfig = CjDevConfig()
    home: Path = Path.cwd() / _CJDEV_HOME_DIR_NAME

    @classmethod
    def find_home_path(cls) -> Path:
        cwd = Path.cwd()
        attempt = cwd / _CJDEV_HOME_DIR_NAME
        firstAttempt = attempt

        while not attempt.is_dir():
            parent = cwd.parent
            if parent == cwd:
                break
            cwd = parent
            attempt = cwd / _CJDEV_HOME_DIR_NAME

        return attempt if attempt.is_dir() else firstAttempt
