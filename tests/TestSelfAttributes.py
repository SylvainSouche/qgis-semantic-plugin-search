"""Every private attribute a plugin class reads must be defined by that class.

Presentation and QgisBridge cannot be imported without qgis, so a slot that
is connected but missing (self.linksView.anchorClicked.connect(self._openLink)
without a _openLink method) only fails when the window opens inside QGIS.
That exact defect shipped in the 0.3.0 package. The check itself lives in
tools/PackageCheck.py, which make dist also runs without a venv.
"""
from __future__ import annotations

from tools.PackageCheck import selfAttributeProblems


def test_every_private_self_attribute_read_is_defined():
    problems = selfAttributeProblems()
    assert not problems, "undefined private attributes:\n" + "\n".join(problems)

# @impl 4be9-6ae4-4ed4-e450
