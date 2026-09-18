"""The workspace config parser, and the two-file error discipline.

The bundled-manifest parser is tested by `test_bundled_manifest`; everything
here is what the workspace layer adds: everything optional, every refusal
naming the file it came from (FR-6), and the same schema gate as the bundled
manifest (FR-5).
"""

from pathlib import Path

import pytest

from cjdev.errors import ManifestError
from cjdev.infra.config import (
    SUPPORTED_SCHEMA_VERSION,
    load_workspace_config,
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

    def test_an_empty_project_table_is_refused_like_an_empty_unit_table(self):
        # The project table is the one people write most, so a forgotten
        # `upstream =` line under a *known* project must be as loud as the
        # same shape under a build unit.
        with pytest.raises(
            ManifestError, match=r"config.toml: project a names no keys"
        ):
            parse_workspace_config("[projects.a]\n", source="config.toml")


class TestWrongTypes:
    def test_a_top_level_key_of_the_wrong_type_is_refused_naming_the_key(self):
        # A string where a table belongs is otherwise an AttributeError at
        # the first `.items()` - a traceback, not a refusal.
        with pytest.raises(ManifestError, match=r"^config.toml: projects must be"):
            parse_workspace_config('projects = "x"\n', source="config.toml")

    def test_a_group_written_as_a_string_is_refused_at_parse_time(self):
        # Iterated one character at a time it would surface as sixteen
        # unknown one-letter projects, far from the line that caused them.
        with pytest.raises(
            ManifestError, match=r"group minimal must be an array of project names"
        ):
            parse_workspace_config(
                '[groups]\nminimal = "cangjie_compiler"\n', source="config.toml"
            )

    def test_a_scalar_body_in_the_projects_table_is_refused_naming_the_entry(self):
        # `_require_table` proves `projects` is a table, not what sits in it:
        # a scalar body would reach `set(body)` as a TypeError - a traceback
        # that takes the `--json` envelope down with it.
        with pytest.raises(
            ManifestError,
            match=r"^config\.toml: project a must be a table, not Integer",
        ):
            parse_workspace_config("[projects]\na = 1\n", source="config.toml")

    def test_a_scalar_build_unit_body_is_refused_like_a_scalar_project(self):
        with pytest.raises(
            ManifestError,
            match=r"^config\.toml: build unit u must be a table, not Integer",
        ):
            parse_workspace_config("[build_units]\nu = 1\n", source="config.toml")

    def test_depends_on_written_as_a_string_is_refused_at_parse_time(self):
        # Iterated one character at a time it would surface as unknown
        # one-letter build units ("depends on unknown unit r"), far from the
        # line that caused it - the defect `_groups` refuses for members.
        with pytest.raises(
            ManifestError,
            match=r"build unit u depends_on must be an array of build-unit names",
        ):
            parse_workspace_config(
                '[build_units.u]\nproject = "a"\npath = "."\ndepends_on = "runtime"\n',
                source="config.toml",
            )

    def test_an_array_in_a_scalar_unit_field_is_refused(self):
        # Through `str()` it would become the plausible-looking path "['a']",
        # failing far from the line that caused it.
        with pytest.raises(
            ManifestError, match=r"build unit u path must be a string, not Array"
        ):
            parse_workspace_config(
                '[build_units.u]\npath = ["a"]\n', source="config.toml"
            )

    def test_an_array_in_a_scalar_project_field_is_refused_like_a_units(self):
        # `upstream` coerces through `str()` just the same way as `path`.
        with pytest.raises(
            ManifestError, match=r"project a upstream must be a string, not Array"
        ):
            parse_workspace_config(
                '[projects.a]\nupstream = ["https://example.invalid/a.git"]\n',
                source="config.toml",
            )


class TestUnreadableFiles:
    def test_bytes_that_are_not_utf8_are_a_refusal_naming_the_file(
        self, tmp_path: Path
    ):
        # The one file users are told to write by hand is the one that
        # arrives unreadable; a traceback is not the answer to that.
        config = tmp_path / ".cjdev" / "config.toml"
        config.parent.mkdir()
        config.write_bytes(b"schema_version = 1\n# \xff\xfe bad\n")

        with pytest.raises(ManifestError, match=r"cannot read .*config\.toml"):
            load_workspace_config(tmp_path)

    def test_a_directory_where_the_file_should_be_is_a_refusal(self, tmp_path: Path):
        config = tmp_path / ".cjdev" / "config.toml"
        config.mkdir(parents=True)

        with pytest.raises(ManifestError, match=r"cannot read .*config\.toml"):
            load_workspace_config(tmp_path)

    def test_an_absent_file_is_still_no_layer(self, tmp_path: Path):
        assert load_workspace_config(tmp_path) is None


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
