"""The one definition and its generated copy.

`spec/undertone.toml` is the definition. `spec/constants.py` is generated from
it by `tools/gen_spec.py`. Both `model/` and `stats/` import the constants:
they share these facts, and share no code.
"""
