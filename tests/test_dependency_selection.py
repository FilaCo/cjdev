from pathlib import PurePosixPath

import pytest

from cjdev.application.manage_dependencies import DependencyRequest
from cjdev.domain.dependencies import Selection, effective
from cjdev.domain.manifest import BuildUnit, ThirdParty
from cjdev.errors import PreconditionError

LLVM = ThirdParty(PurePosixPath("third_party/llvm"), "workspace-fork", "pinned")
KEY = ("compiler", "llvm")


@pytest.mark.parametrize(
    ("request_ref", "upstream", "previous", "selection", "expected_source"),
    [
        ("main", None, None, Selection("main"), "workspace-fork"),
        ("main", "upstream", None, Selection("main", "upstream"), "upstream"),
        (
            "revision",
            None,
            Selection("main", "upstream"),
            Selection("revision", "upstream"),
            "upstream",
        ),
        (None, None, Selection("main", "upstream"), None, "workspace-fork"),
    ],
)
def test_selection_and_inheritance(
    request_ref, upstream, previous, selection, expected_source
):
    # Arrange
    request = DependencyRequest(*KEY, request_ref, upstream)

    # Act
    selected = request.decide(previous)
    source = effective("compiler", LLVM, {} if selected is None else {KEY: selected})

    # Assert
    assert selected == selection
    assert (source.upstream, source.ref) == (expected_source, request_ref or LLVM.ref)


def test_invalid_request_names_the_available_sources():
    # Arrange
    request = DependencyRequest("compiler", "unknown", "main")
    unit = BuildUnit(
        "compiler", "compiler", PurePosixPath("."), (), third_party=(LLVM,)
    )

    # Act
    with pytest.raises(PreconditionError) as failure:
        request.validate(unit)

    # Assert
    assert "Known dependencies: llvm" in str(failure.value)
