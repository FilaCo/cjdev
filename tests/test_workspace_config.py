"""The workspace config parser, and the two-file error discipline.

The bundled-manifest parser is tested by `test_bundled_manifest`; everything
here is what the workspace layer adds: everything optional, every refusal
naming the file it came from (FR-6), and the same schema gate as the bundled
manifest (FR-5).
"""

import pytest

from cjdev.errors import ManifestError
from cjdev.infra.config import (
    SUPPORTED_SCHEMA_VERSION,
    parse_workspace_config,
)


class TestEverythingOptional:
    def test_a_comment_only_file_is_an_empty_override(self):
        # Exactly what `init` writes: no keys, no overrides, valid all the
        # same (FR-4).
        config = parse_workspace_config(
            "# cjdev workspace configuration.\n#\n# nothing here.\n",
            source="config.toml",
        )

        assert config.projects == {}
        assert config.build_units == {}
        assert config.groups == {}
        assert config.default_group is None
        assert config.schema_version is None

    def test_a_partial_project_override_carries_only_what_it_names(self):
        config = parse_workspace_config(
            '[projects.a]\nupstream = "https://mirror/a.git"\n', source="config.toml"
        )

        override = config.projects["a"]
        assert override.upstream == "https://mirror/a.git"
        assert override.role is None
        assert override.default_branch is None

    def test_an_explicit_empty_depends_on_is_not_the_missing_one(self):
        config = parse_workspace_config(
            '[build_units.u]\nproject = "a"\npath = "."\ndepends_on = []\n',
            source="config.toml",
        )

        assert config.build_units["u"].depends_on == ()

    def test_an_omitted_depends_on_inherits(self):
        config = parse_workspace_config(
            '[build_units.u]\nproject = "a"\npath = "."\n', source="config.toml"
        )

        assert config.build_units["u"].depends_on is None


class TestRefusalsNameTheFile:
    """FR-6: with two files in play, an error that just says "the manifest"
    names nothing."""

    def test_broken_toml_is_reported_with_the_workspace_file(self):
        with pytest.raises(ManifestError, match=r"^config.toml is not valid TOML"):
            parse_workspace_config("schema_version = = 1", source="config.toml")

    def test_an_unknown_key_is_reported_with_the_workspace_file(self):
        with pytest.raises(ManifestError, match=r"^config.toml:.*nope"):
            parse_workspace_config(
                '[projects.a]\nnope = 1\nupstream = "x"\n', source="config.toml"
            )

    def test_an_unknown_role_lists_the_known_ones(self):
        with pytest.raises(ManifestError, match=r"^config.toml:.*Known roles"):
            parse_workspace_config('[projects.a]\nrole = "wat"\n', source="config.toml")

    def test_an_empty_unit_table_is_refused_rather_than_silently_inherited(self):
        # A bare table header overrides nothing; honouring it would read as
        # success while saying nothing, which is worse than the refusal.
        with pytest.raises(
            ManifestError, match=r"config.toml: build unit u names no keys"
        ):
            parse_workspace_config("[build_units.u]\n", source="config.toml")


class TestSchemaVersionGate:
    def test_a_future_version_is_refused_naming_the_workspace_file(self):
        # FR-5: the workspace file gets the same gate as the bundled manifest.
        with pytest.raises(
            ManifestError, match=r"^config\.toml declares.*Upgrade cjdev"
        ):
            parse_workspace_config("schema_version = 99\n", source="config.toml")

    def test_the_supported_version_is_accepted_and_carried(self):
        config = parse_workspace_config(
            f"schema_version = {SUPPORTED_SCHEMA_VERSION}\n", source="config.toml"
        )

        assert config.schema_version == SUPPORTED_SCHEMA_VERSION
