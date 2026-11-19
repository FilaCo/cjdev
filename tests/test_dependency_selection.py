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
    selected = DependencyRequest(*KEY, request_ref, upstream).decide(previous)
    source = effective("compiler", LLVM, {} if selected is None else {KEY: selected})
    assert selected == selection
    assert (source.upstream, source.ref) == (expected_source, request_ref or LLVM.ref)


def test_invalid_request_names_the_available_sources():
    unit = BuildUnit(
        "compiler", "compiler", PurePosixPath("."), (), third_party=(LLVM,)
    )
    with pytest.raises(PreconditionError, match="Known dependencies: llvm"):
        DependencyRequest("compiler", "unknown", "main").validate(unit)
