from pathlib import Path
from typing import final

from pydantic import BaseModel


@final
class Repo(BaseModel):
    path: Path
    origin: str
    upstream: str
    default_branch: str
