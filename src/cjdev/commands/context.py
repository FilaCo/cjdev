from dataclasses import dataclass
from pathlib import Path
from typing import Optional, final

from pydantic import BaseModel, model_validator
from pydantic_core import Url
from tomlkit import dumps, item, parse, register_encoder
from tomlkit.exceptions import ConvertError


@final
@dataclass
class CjDevContext:
    config_path: Path
    config: "Config"


@final
class ContainerConfig(BaseModel):
    use_container: bool = False
    container_name: Optional[str] = None
    container_workdir: Optional[Path] = None

    @model_validator(mode="after")
    def validate_fields_when_container_used(self) -> "ContainerConfig":
        if not self.use_container:
            return self

        missing_fields = []
        if not self.container_name:
            missing_fields.append("container_name")
        if not self.container_workdir:
            missing_fields.append("container_workdir")
        if missing_fields:
            raise ValueError(f"Missing required fields: {', '.join(missing_fields)}")

        return self


@final
class ProjectsConfig(BaseModel):
    cangjie_compiler: Optional["ProjectConfig"] = None
    cangjie_runtime: Optional["ProjectConfig"] = None
    cangjie_test: Optional["ProjectConfig"] = None
    cangjie_multiplatform_interop: Optional["ProjectConfig"] = None
    cangjie_stdx: Optional["ProjectConfig"] = None
    cangjie_tools: Optional["ProjectConfig"] = None


_CONFIG_FILE_NAME = "cjdev.toml"


@final
class Config(BaseModel):
    container: ContainerConfig = ContainerConfig()
    projects: Optional["ProjectsConfig"] = None

    def load(fpath: Path) -> "Config":
        text = fpath.read_text()
        parsed = parse(text)
        config = Config.model_validate(parsed)

        return config

    def save(self, path: Path) -> None:
        if not path.is_file():
            path.joinpath(_CONFIG_FILE_NAME)

        dict = self.model_dump(exclude_none=True)
        toml = dumps(dict)
        path.write_text(toml)

    def find_config() -> Path:
        cwd = Path.cwd()
        config = cwd / _CONFIG_FILE_NAME
        firstAttempt = config

        while not config.is_file():
            parent = cwd.parent
            if parent == cwd:
                break
            cwd = parent
            config = cwd / _CONFIG_FILE_NAME

        return config if config.is_file() else firstAttempt


@final
class ProjectConfig(BaseModel):
    path: Path
    origin_url: Url
    upstream_url: Url
    default_branch: str


@register_encoder
def _path_encoder(obj, _parent=None, _sort_keys=False):
    if isinstance(obj, Path):
        return item(obj.as_posix())

    raise ConvertError("Not a Path")


@register_encoder
def _url_encoder(obj, _parent=None, _sort_keys=False):
    if isinstance(obj, Url):
        return item(str(obj))

    raise ConvertError("Not a Url")
