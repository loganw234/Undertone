"""The one conftest.py, at the root, and the lead's.

It holds no fixture and no hook. It is here so that pytest puts the tree's root
on the import path however it is started: `python -m pytest` and a bare `pytest`
then both find `spec`, `model` and `stats`.

No other conftest.py and no pytest.ini belongs in this tree. Either can deselect
tests, and the `model-tests` stage would then run what is left.
"""
