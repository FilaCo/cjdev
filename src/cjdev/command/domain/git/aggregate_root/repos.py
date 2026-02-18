from typing import List, final

from pydantic import BaseModel

from cjdev.command.domain.git.entity.repo import Repo


@final
class Repos(BaseModel):
    inner: List[Repo]

    def switch(self):
        pass

    def sync(self):
        pass

    def upload(self):
        pass
