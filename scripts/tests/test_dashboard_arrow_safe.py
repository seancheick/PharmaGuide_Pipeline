"""Regression test for the dashboard Arrow-serialization fix.

Blob-derived ingredient tables (Inspector) have object columns with mixed types
across products — e.g. `is_additive` is bool on some rows, NaN on others; other
columns mix int/bool or carry lists/dicts. pyarrow then raises 'Expected integer,
got bool' and Streamlit logs a traceback. arrow_safe() must make any such frame
serializable.
"""
import pandas as pd
import pyarrow as pa

from scripts.dashboard.components.data_table import arrow_safe


def _arrow_ok(df: pd.DataFrame) -> bool:
    try:
        pa.Table.from_pandas(df)
        return True
    except Exception:
        return False


def test_mixed_bool_none_column_is_arrow_safe():
    # is_additive: bool on some rows, missing (NaN) on others -> object dtype.
    df = pd.DataFrame([
        {"name": "Cellulose", "is_additive": True},
        {"name": "Magnesium Stearate"},  # no is_additive -> NaN
        {"name": "Silica", "is_additive": False},
    ])
    assert _arrow_ok(arrow_safe(df))  # serializable after the fix


def test_mixed_bool_int_column_is_arrow_safe():
    # The exact reported failure: 'Expected integer, got bool' / 'Could not
    # convert 0 with type int: tried to convert to boolean'. Reliably un-Arrow
    # raw; arrow_safe must fix it.
    df = pd.DataFrame({"flag": [True, True, 0]})
    assert not _arrow_ok(df)
    assert _arrow_ok(arrow_safe(df))


def test_list_and_dict_columns_are_arrow_safe():
    df = pd.DataFrame([
        {"name": "A", "forms": ["a", "b"], "identifiers": {"cas": "1"}},
        {"name": "B", "forms": [], "identifiers": {}},
    ])
    assert _arrow_ok(arrow_safe(df))


def test_clean_numeric_and_string_columns_preserved():
    df = pd.DataFrame({"score": [1.0, 2.0], "name": ["a", "b"]})
    out = arrow_safe(df)
    assert out["score"].tolist() == [1.0, 2.0]   # numeric dtype untouched
    assert out["name"].tolist() == ["a", "b"]
    assert _arrow_ok(out)


def test_none_and_nan_render_as_empty_string():
    df = pd.DataFrame([{"x": True}, {"x": None}])
    out = arrow_safe(df)
    assert out["x"].tolist() == ["True", ""]
