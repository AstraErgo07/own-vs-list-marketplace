"""smoke_test_app.py - headless check that every page loads and the decision buttons work.
Run:  python smoke_test_app.py   (any test rows in the local decision log are removed afterwards)
"""
import os
import sys
from pathlib import Path

from streamlit.testing.v1 import AppTest

os.chdir(Path(__file__).parent)
sys.path.insert(0, ".")
PAGE = "app_pages/own_vs_list_page.py"
DATA = Path("own_vs_list/listings.csv")
LOG = Path("own_vs_list/decisions.csv")
BACKUP = LOG.read_bytes() if LOG.exists() else None
try:
    for page in [PAGE, "app_pages/method_page.py"]:
        at = AppTest.from_file(page, default_timeout=60).run()
        print(page, "exceptions:", [e.value for e in at.exception], "| dataframes:", len(at.dataframe))
        assert not at.exception, page
        assert any(c.value.startswith("Own vs List v1.0") for c in at.caption), page
    at = AppTest.from_file(PAGE, default_timeout=60).run()
    cols = [list(d.value.columns) for d in at.dataframe]
    assert sum(any("Avg selling price per unit" in c for c in cs) for cs in cols) >= 1, cols
    assert any(e.label == "How these numbers are worked out" for e in at.expander)
    assert any("1P contribution per unit" in str(t.value.to_dict()) for t in at.table)
    [b for b in at.button if b.key and b.key.startswith("ovl_ovr_")][0].click().run()
    print("override w/o reason errors:", [e.value for e in at.error])
    assert at.error
    [b for b in at.button if b.key and b.key.startswith("ovl_acc_")][0].click().run()
    print("accept success:", [s.value for s in at.success])
    assert at.success and LOG.exists()
    hidden = DATA.with_suffix(".bak")
    DATA.rename(hidden)
    try:
        at = AppTest.from_file(PAGE, default_timeout=60).run()
        assert not at.exception and any("Something went wrong" in e.value for e in at.error), at.exception
        print("error wrapper ok")
    finally:
        hidden.rename(DATA)
    at = AppTest.from_file("streamlit_app.py", default_timeout=60).run()
    ok_footer = any("Made by Ami Sata" in c.value and "v1.0" in c.value
                    and "made-up example products" in c.value.lower()
                    for c in at.caption)
    assert not at.exception and ok_footer and any("Own stock vs marketplace" in t.value for t in at.title)
    print("launcher ok")
finally:
    if BACKUP is None:
        LOG.unlink(missing_ok=True)
    else:
        LOG.write_bytes(BACKUP)
print("SMOKE TEST PASSED")
