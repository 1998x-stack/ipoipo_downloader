from hypothesis import given, strategies as st

from ipoipo.artifacts.naming import safe_filename


@given(st.text())
def test_filename_has_no_path_separators(raw):
    value = safe_filename(raw)
    assert value
    assert len(value) <= 120
    assert "/" not in value
    assert "\\" not in value
    assert "\x00" not in value
    assert value not in {".", ".."}
