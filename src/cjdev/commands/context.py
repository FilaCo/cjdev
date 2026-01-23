from pathlib import Path
from typing import Optional, Tuple, final

from pydantic import BaseModel, model_validator
from pydantic_core import Url
from tomlkit import parse


@final
class CjDevContext(BaseModel):
    config_path: Path
    config: "Config"


@final
class ContainerConfig(BaseModel):
    use_container: bool = False
    host_workdir: Optional[Path] = None
    container_workdir: Optional[Path] = None
    container_name: str = "cjdev"

    @model_validator(mode="after")
    def validate_fields_when_container_used(self) -> "ContainerConfig":
        if not self.use_container:
            return self

        missing_fields = []
        if not self.host_workdir:
            missing_fields.append("host_workdir")
        if not self.container_workdir:
            missing_fields.append("container_workdir")

        if missing_fields:
            raise ValueError(f"Missing required fields: {', '.join(missing_fields)}")

        return self


@final
class ProjectConfig(BaseModel):
    path: Path
    origin_url: Url
    upstream_url: Url
    branch: str


@final
class ProjectsConfig(BaseModel):
    cangjie_compiler: Optional[ProjectConfig] = None
    cangjie_runtime: Optional[ProjectConfig] = None
    cangjie_test: Optional[ProjectConfig] = None
    cangjie_multiplatform_interop: Optional[ProjectConfig] = None
    cangjie_stdx: Optional[ProjectConfig] = None
    cangjie_tools: Optional[ProjectConfig] = None


@final
class Config(BaseModel):
    container: ContainerConfig = ContainerConfig()
    projects: ProjectsConfig = ProjectsConfig()

    def load_or_default() -> Tuple[Path, "Config"]:
        config = Config()
        config_path = _find_config()

        if config_path.is_file():
            text = config_path.read_text()
            parsed = parse(text)
            config = Config.model_validate(parsed)

        return (config_path, config)


def _find_config() -> Path:
    config_file_name = "cjdev.toml"
    cwd = Path.cwd()
    config = cwd.joinpath(config_file_name)
    attempts = []

    while not config.is_file():
        attempts.append(config)
        parent = cwd.parent
        if parent == cwd:
            break
        cwd = parent
        config = cwd.joinpath(config_file_name)

    if not config.is_file():
        # TODO: print warning with attempts
        return attempts[0]

    return config
