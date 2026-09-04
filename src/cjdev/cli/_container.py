from functools import cached_property

from cjdev.commands import InitializeWorkspace
from cjdev.domain import WorkspaceRepo
from cjdev.infra.repo import FileSystemWorkspaceRepo
from cjdev.query import GetWorkspaceStatus


class Container:
    @cached_property
    def initialize_workspace(self) -> InitializeWorkspace:
        return InitializeWorkspace(self.workspace_repo)

    @cached_property
    def get_workspace_status(self) -> GetWorkspaceStatus:
        return GetWorkspaceStatus()

    @cached_property
    def workspace_repo(self) -> WorkspaceRepo:
        return FileSystemWorkspaceRepo()
