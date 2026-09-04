from typing import final

from cjdev.domain import WorkspaceRepo


@final
class InitializeWorkspace:
    def __init__(self, workspace_repo: WorkspaceRepo) -> None:
        self._workspace_repo = workspace_repo

    def perform(self) -> None:
        pass
