from pathlib import Path
from typing import Optional, final

from pydantic import BaseModel, model_validator
from tomlkit import dumps, parse


@final
class ContainerConfig(BaseModel):
    use_container: bool = False
    container_name: Optional[str] = None

    @model_validator(mode="after")
    def validate_fields_when_container_used(self) -> "ContainerConfig":
        if not self.use_container:
            return self

        missing_fields = []
        if not self.container_name:
            missing_fields.append("container_name")
        if missing_fields:
            raise ValueError(f"Missing required fields: {', '.join(missing_fields)}")

        return self


@final
class ProjectConfig(BaseModel):
    path: str
    origin_url: str
    upstream_url: str
    default_branch: str


@final
class ProjectsConfig(BaseModel):
    cangjie_compiler: Optional[ProjectConfig] = None
    cangjie_runtime: Optional[ProjectConfig] = None
    cangjie_test: Optional[ProjectConfig] = None
    cangjie_multiplatform_interop: Optional[ProjectConfig] = None
    cangjie_stdx: Optional[ProjectConfig] = None
    cangjie_tools: Optional[ProjectConfig] = None


CJDEV_CONFIG_FILE_NAME = "config.toml"


@final
class CjDevConfig(BaseModel):
    container: ContainerConfig = ContainerConfig()
    projects: ProjectsConfig = ProjectsConfig()

    @classmethod
    def load(cls, dir: Path) -> "CjDevConfig":
        fpath = dir / CJDEV_CONFIG_FILE_NAME
        text = fpath.read_text()
        parsed = parse(text)
        config = CjDevConfig.model_validate(parsed)

        return config

    def save(self, path: Path) -> None:
        dict = self.model_dump(exclude_none=True)
        toml = dumps(dict)
        path.write_text(toml)
