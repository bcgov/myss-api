"""Tests for SRTypeRegistry (Task 19)."""
from app.domains.service_requests.models import SRType
from app.domains.service_requests.sr_type_registry import SRTypeRegistry


def test_dynamic_types_return_true():
    assert SRTypeRegistry.is_dynamic(SRType.ASSIST) is True
    assert SRTypeRegistry.is_dynamic(SRType.CRISIS_FOOD) is True
    assert SRTypeRegistry.is_dynamic(SRType.PWD_DESIGNATION) is True


def test_non_dynamic_types_return_false():
    """DIRECT_DEPOSIT and BUS_PASS are non-dynamic (simple submit flow)."""
    assert SRTypeRegistry.is_dynamic(SRType.DIRECT_DEPOSIT) is False
    assert SRTypeRegistry.is_dynamic(SRType.BUS_PASS) is False
