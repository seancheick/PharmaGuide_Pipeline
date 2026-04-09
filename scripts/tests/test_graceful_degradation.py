import sys
from unittest.mock import MagicMock
from pathlib import Path

# Better Mock streamlit
class MockStreamlit(MagicMock):
    def __getattr__(self, name):
        if name in ['sidebar', 'expander']:
            return MockStreamlit()
        return super().__getattr__(name)
    
    def columns(self, spec):
        n = spec if isinstance(spec, int) else len(spec)
        return [MockStreamlit() for _ in range(n)]
        
    def tabs(self, labels):
        return [MockStreamlit() for _ in range(len(labels))]
    
    def __enter__(self):
        return self
        
    def __exit__(self, *args):
        pass

    def __format__(self, format_spec):
        return "MockValue"

mock_st = MockStreamlit()
# Passthrough decorators
def passthrough(func=None, **kwargs):
    if func is not None: return func
    return lambda f: f
mock_st.cache_resource = passthrough
mock_st.cache_data = passthrough

sys.modules["streamlit"] = mock_st

from scripts.dashboard.config import DashboardConfig
from scripts.dashboard.data_loader import load_dashboard_data
from scripts.dashboard.views import render_inspector, render_health, render_quality
from scripts.dashboard.views.inspector import render_drill_down

def test_graceful_degradation():
    print("Testing graceful degradation with missing DB...")
    config = DashboardConfig(
        scan_dir=Path("non_existent_scan").resolve(),
        build_root=Path("non_existent_build").resolve()
    )
    
    data = load_dashboard_data(config)
    
    try:
        render_inspector(data)
        print("render_inspector: OK")
        render_health(data)
        print("render_health: OK")
        render_quality(data)
        print("render_quality: OK")
    except Exception as e:
        print(f"FAILED: Exception raised during render: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
        
    print("Graceful degradation test PASSED.")


def test_inspector_drill_down_real_product():
    config = DashboardConfig(
        scan_dir=Path("scripts/products").resolve(),
        build_root=Path("scripts/final_db_output").resolve()
    )

    data = load_dashboard_data(config)

    if data.db_conn is None:
        return

    row = data.db_conn.execute("SELECT dsld_id FROM products_core LIMIT 1").fetchone()
    assert row is not None

    render_drill_down(row["dsld_id"], data)

if __name__ == "__main__":
    test_graceful_degradation()
