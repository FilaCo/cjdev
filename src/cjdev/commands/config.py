from pathlib import Path
from typing import Optional, final

from pydantic import BaseModel, model_validator
from tomlkit import parse


@final
class ContainerConfig(BaseModel):
    use_container: bool = False
    host_workdir: Optional[Path] = None
    container_workdir: Optional[Path] = None
    container_name: str = "cjdev"

    @model_validator(mode="after")
    def validate_fields_when_container_used(self) -> ContainerConfig:
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
class Config(BaseModel):
    container: Optional[ContainerConfig] = None

    def load_or_default() -> Config:
        path = _find_config()

        if not path.exists() or not path.is_file():
            return Config()

        try:
            return Config.load(path)
        except (FileNotFoundError, NotImplementedError) as _:
            # TODO: print error
            return Config()

    def load(config: Path) -> Config:
        if not config.exists():
            raise FileNotFoundError(f"Config file not found at {config}")

        if config.is_dir():
            raise NotImplementedError(f"Config directory is not supported {config}")

        text = config.read_text()
        parsed = parse(text)

        return Config.model_validate(parsed)


def _find_config() -> Path:
    config_file_name = "cjdev.toml"
    cwd = Path.cwd()
    config = cwd.joinpath(config_file_name)
    attempts = []

    while not config.exists() or not config.is_file():
        attempts.append(config)
        parent = cwd.parent
        if parent == cwd:
            break
        cwd = parent
        config = cwd.joinpath(config_file_name)

    if not config.exists() and not config.is_file():
        # TODO: print warning with attempts
        return attempts[0]

    return config
