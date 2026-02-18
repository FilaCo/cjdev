from pathlib import Path
from typing import final

from pydantic import BaseModel

from cjdev.shared.config import CjDevConfig

CJDEV_HOME_DIR_NAME = ".cjdev"


@final
class CjDevContext(BaseModel):
    verbose: bool = False
    cfg: CjDevConfig = CjDevConfig()
    home: Path

    @classmethod
    def find_home(cls) -> Path:
        cwd = Path.cwd()
        attempt = cwd / CJDEV_HOME_DIR_NAME
        firstAttempt = attempt

        while not attempt.is_dir():
            parent = cwd.parent
            if parent == cwd:
                break
            cwd = parent
            attempt = cwd / CJDEV_HOME_DIR_NAME

        return attempt if attempt.is_dir() else firstAttempt
