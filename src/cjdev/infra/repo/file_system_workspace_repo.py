from pathlib import Path

from cjdev.domain import (
    UninitializedWorkspaceState,
    Workspace,
    WorkspaceId,
    WorkspaceRepo,
)


class FileSystemWorkspaceRepo(WorkspaceRepo):
    def get_by_id(self, id: WorkspaceId) -> Workspace:
        ws_root = Path(id.value)
        cjdev_home_dir = ws_root / ".cjdev"

        if not cjdev_home_dir.is_dir():
            return Workspace(id, UninitializedWorkspaceState())

        raise NotImplementedError
