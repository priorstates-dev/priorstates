"""The service seam: plugins register managed-service descriptors; the registry
flattens them (dict or list) for the desktop GUI to start/stop."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from priorstates.core.plugins import Registry  # noqa: E402


def test_services_flatten_dict_and_list():
    reg = Registry()
    reg.add_service(lambda: {"name": "a", "argv": ["x"]})
    reg.add_service(lambda: [{"name": "b"}, {"name": "c"}])
    names = sorted(s["name"] for s in reg.services())
    assert names == ["a", "b", "c"]


def test_broken_service_hook_does_not_break_others():
    reg = Registry()
    reg.add_service(lambda: (_ for _ in ()).throw(RuntimeError("boom")))
    reg.add_service(lambda: {"name": "ok"})
    assert [s["name"] for s in reg.services()] == ["ok"]


def test_no_services_by_default():
    assert Registry().services() == []
