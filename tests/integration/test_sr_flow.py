"""Integration test for full SR lifecycle.

Mocks at the SiebelSRClient boundary so that the real ServiceRequestService
logic runs, while the external Siebel HTTP calls are stubbed.
The AsyncSession is also mocked since we don't have a test database.
"""
import pytest
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch
import jwt as pyjwt
from httpx import AsyncClient, ASGITransport

from sqlalchemy import select, update, delete

from app.main import app
from app.services.icm.service_requests import SiebelSRClient
from app.domains.account.pin_service import PINService
from app.models.service_requests import SRDraft
from app.domains.service_requests.models import (
    SRType, SRDraftResponse, SRSubmitResponse, DynamicFormSchema,
    DynamicFormType, DynamicFormPage, DynamicFormField, SRListResponse, SRSummary,
    SRDetailResponse,
)
from app.domains.service_requests.service import ServiceRequestService
from app.routers.service_requests import _get_sr_service


def make_token(role="CLIENT", secret="change-me-in-production"):
    return pyjwt.encode({"sub": "user1", "role": role}, secret, algorithm="HS256")


_NOW = datetime(2024, 6, 1, 12, 0, 0, tzinfo=timezone.utc)


def _stub_siebel_client() -> SiebelSRClient:
    """Create a SiebelSRClient stub with mocked methods for the full lifecycle."""
    client = AsyncMock(spec=SiebelSRClient)

    # create_sr returns an sr_id
    client.create_sr = AsyncMock(return_value={"sr_id": "SR-FLOW-001"})

    # get_sr_list returns the submitted SR
    client.get_sr_list = AsyncMock(return_value={
        "items": [{
            "sr_id": "SR-FLOW-001",
            "sr_type": "ASSIST",
            "sr_number": "SR-NUM-FLOW-001",
            "status": "Submitted",
            "client_name": "Test User",
            "created_at": "2024-06-01T12:00:00+00:00",
        }],
        "total": 1,
    })

    # get_eligible_types
    client.get_eligible_types = AsyncMock(return_value={"types": []})

    # finalize_sr_form returns sr_number
    client.finalize_sr_form = AsyncMock(return_value={"sr_number": "SR-NUM-FLOW-001"})

    # get_sr_detail
    client.get_sr_detail = AsyncMock(return_value={
        "sr_id": "SR-FLOW-001",
        "sr_type": "ASSIST",
        "sr_number": "SR-NUM-FLOW-001",
        "status": "Submitted",
        "client_name": "Test User",
        "created_at": "2024-06-01T12:00:00+00:00",
        "answers": {"reason": "Test"},
        "attachments": [],
    })

    return client


def _mock_session():
    """Create a mock AsyncSession that simulates draft storage in memory.

    Handles ORM statement objects (select, update, delete) and session.add()
    for SRDraft model instances.
    """
    session = AsyncMock()
    drafts: dict[str, dict] = {}

    # Capture session.add(draft_obj) calls — store the ORM object as a draft
    _pending_adds: list[SRDraft] = []

    def mock_add(obj):
        if isinstance(obj, SRDraft):
            _pending_adds.append(obj)

    session.add = mock_add

    async def mock_commit():
        # Flush any pending adds
        for obj in _pending_adds:
            drafts[obj.sr_id] = {
                "sr_id": obj.sr_id,
                "user_id": obj.user_id,
                "sr_type": obj.sr_type,
                "draft_json": obj.draft_json,
                "updated_at": obj.updated_at,
            }
        _pending_adds.clear()

    session.commit = mock_commit

    def _extract_sr_id_from_whereclause(clause) -> str | None:
        """Walk a BinaryExpression / BooleanClauseList to find sr_id literal."""
        if clause is None:
            return None
        compiled = str(clause.compile(compile_kwargs={"literal_binds": True}))
        # Look for sr_drafts.sr_id = 'VALUE' pattern
        import re
        m = re.search(r"sr_id\s*=\s*'([^']+)'", compiled)
        return m.group(1) if m else None

    async def mock_execute(stmt):
        result = MagicMock()
        compiled_sql = str(stmt.compile())

        if isinstance(stmt, type(select(SRDraft))) or "SELECT" in compiled_sql.upper():
            # SELECT query
            sr_id = _extract_sr_id_from_whereclause(stmt.whereclause)
            if sr_id and sr_id in drafts:
                d = drafts[sr_id]
                row = MagicMock(spec=SRDraft)
                row.sr_id = d["sr_id"]
                row.user_id = d.get("user_id", "")
                row.sr_type = d["sr_type"]
                row.draft_json = d["draft_json"]
                row.updated_at = d["updated_at"]
                result.scalar_one_or_none.return_value = row
            else:
                result.scalar_one_or_none.return_value = None
        elif "UPDATE" in compiled_sql.upper():
            sr_id = _extract_sr_id_from_whereclause(stmt.whereclause)
            if sr_id and sr_id in drafts:
                # Extract values from the compiled statement's params
                vals = stmt.compile().params
                if "draft_json" in vals:
                    drafts[sr_id]["draft_json"] = vals["draft_json"]
                if "updated_at" in vals:
                    drafts[sr_id]["updated_at"] = vals["updated_at"]
                else:
                    drafts[sr_id]["updated_at"] = _NOW
                d = drafts[sr_id]
                row = MagicMock(spec=SRDraft)
                row.sr_id = d["sr_id"]
                row.user_id = d.get("user_id", "")
                row.sr_type = d["sr_type"]
                row.draft_json = d["draft_json"]
                row.updated_at = d["updated_at"]
                result.scalar_one_or_none.return_value = row
                result.rowcount = 1
            else:
                result.scalar_one_or_none.return_value = None
                result.rowcount = 0
        elif "DELETE" in compiled_sql.upper():
            sr_id = _extract_sr_id_from_whereclause(stmt.whereclause)
            if sr_id:
                drafts.pop(sr_id, None)
            result.rowcount = 1
        else:
            result.scalar_one_or_none.return_value = None
            result.rowcount = 0

        return result

    session.execute = mock_execute
    session.rollback = AsyncMock()
    return session


async def test_full_sr_lifecycle():
    """Create → save draft → get draft → get form → submit → list shows submitted SR.

    Uses real ServiceRequestService with mocked SiebelSRClient and AsyncSession.
    """
    client = _stub_siebel_client()
    session = _mock_session()
    pin_svc = PINService(client=AsyncMock())
    pin_svc.validate = AsyncMock(return_value=True)
    svc = ServiceRequestService(sr_client=client, session=session, pin_service=pin_svc)

    app.dependency_overrides[_get_sr_service] = lambda: svc

    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            token = make_token()
            headers = {"Authorization": f"Bearer {token}"}

            # 1. Create SR
            r = await ac.post("/service-requests", json={"sr_type": "ASSIST"}, headers=headers)
            assert r.status_code == 201
            sr_id = r.json()["sr_id"]
            assert sr_id == "SR-FLOW-001"
            client.create_sr.assert_awaited_once_with("ASSIST", "user1")

            # 2. Save draft
            r = await ac.put(
                f"/service-requests/{sr_id}/form",
                json={"answers": {"reason": "Test"}, "page_index": 0},
                headers=headers,
            )
            assert r.status_code == 200
            assert r.json()["draft_json"]["answers"]["reason"] == "Test"

            # 3. Get draft — verify it was persisted
            r = await ac.get(f"/service-requests/{sr_id}/draft", headers=headers)
            assert r.status_code == 200
            assert r.json()["sr_id"] == sr_id
            assert r.json()["draft_json"]["answers"]["reason"] == "Test"

            # 4. Get form schema
            r = await ac.get(f"/service-requests/{sr_id}/form", params={"sr_type": "ASSIST"}, headers=headers)
            assert r.status_code == 200
            assert r.json()["total_pages"] == 1

            # 5. Submit
            r = await ac.post(
                f"/service-requests/{sr_id}/submit",
                json={"pin": "1234", "declaration_accepted": True},
                headers=headers,
            )
            assert r.status_code == 200
            assert r.json()["sr_number"] == "SR-NUM-FLOW-001"
            client.finalize_sr_form.assert_awaited_once()

            # 6. Verify draft was deleted — GET draft returns 404
            r = await ac.get(f"/service-requests/{sr_id}/draft", headers=headers)
            assert r.status_code == 404

            # 7. List — submitted SR appears
            r = await ac.get("/service-requests", headers=headers)
            assert r.status_code == 200
            assert r.json()["items"][0]["sr_number"] == "SR-NUM-FLOW-001"
    finally:
        app.dependency_overrides.pop(_get_sr_service, None)


async def test_sr_detail_not_found():
    """GET /service-requests/{sr_id} returns 404 when SR does not exist."""
    client = AsyncMock(spec=SiebelSRClient)
    client.get_sr_detail = AsyncMock(return_value=None)
    svc = ServiceRequestService(sr_client=client, session=None)

    app.dependency_overrides[_get_sr_service] = lambda: svc

    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            token = make_token()
            headers = {"Authorization": f"Bearer {token}"}

            r = await ac.get("/service-requests/NONEXISTENT-SR-ID", headers=headers)
            assert r.status_code == 404
            assert "not found" in r.json()["detail"].lower()
    finally:
        app.dependency_overrides.pop(_get_sr_service, None)


async def test_submit_declaration_not_accepted_rejected():
    """POST /service-requests/{sr_id}/submit returns 422 when declaration_accepted is false."""
    client = AsyncMock(spec=SiebelSRClient)
    svc = ServiceRequestService(sr_client=client, session=None)

    app.dependency_overrides[_get_sr_service] = lambda: svc

    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            token = make_token()
            headers = {"Authorization": f"Bearer {token}"}

            r = await ac.post(
                "/service-requests/SR-FLOW-001/submit",
                json={"pin": "1234", "declaration_accepted": False},
                headers=headers,
            )
            assert r.status_code == 422
            # finalize should never be called since Pydantic rejects the payload
            client.finalize_sr_form.assert_not_called()
    finally:
        app.dependency_overrides.pop(_get_sr_service, None)


async def test_sr_detail_returned_successfully():
    """GET /service-requests/{sr_id} returns full detail when SR exists."""
    client = AsyncMock(spec=SiebelSRClient)
    client.get_sr_detail = AsyncMock(return_value={
        "sr_id": "SR-DETAIL-001",
        "sr_type": "DIET",
        "sr_number": "SR-NUM-DETAIL-001",
        "status": "Submitted",
        "client_name": "Jane Doe",
        "created_at": "2024-06-01T12:00:00+00:00",
        "answers": {"dietary_need": "gluten-free"},
        "attachments": ["doc1.pdf"],
    })
    svc = ServiceRequestService(sr_client=client, session=None)

    app.dependency_overrides[_get_sr_service] = lambda: svc

    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            token = make_token()
            headers = {"Authorization": f"Bearer {token}"}

            r = await ac.get("/service-requests/SR-DETAIL-001", headers=headers)
            assert r.status_code == 200
            body = r.json()
            assert body["sr_id"] == "SR-DETAIL-001"
            assert body["sr_number"] == "SR-NUM-DETAIL-001"
            assert body["status"] == "Submitted"
            assert body["answers"]["dietary_need"] == "gluten-free"
            assert "doc1.pdf" in body["attachments"]
    finally:
        app.dependency_overrides.pop(_get_sr_service, None)
