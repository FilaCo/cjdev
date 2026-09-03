"""Path algebra for a workspace, parameterised by its root.

Pure and root-relative on purpose: that is what turns ENV-5 (a fixed path inside the
container) into a different root rather than a second code path.
"""
