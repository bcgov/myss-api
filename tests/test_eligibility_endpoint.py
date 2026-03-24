# tests/test_eligibility_endpoint.py
import pytest
from decimal import Decimal
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_calculate_eligible_single(client: AsyncClient):
    """POST /eligibility-estimator/calculate returns eligible=true for valid low-income single."""
    response = await client.post(
        "/eligibility-estimator/calculate",
        json={
            "relationship_status": "SINGLE",
            "num_dependants": 0,
            "applicant_pwd": False,
            "spouse_pwd": False,
            "monthly_income": "800.00",
            "spouse_monthly_income": "0.00",
            "primary_vehicle_value": "0.00",
            "other_vehicle_value": "0.00",
            "other_asset_value": "0.00",
        },
    )
    assert response.status_code == 200
    data = response.json()
    assert data["eligible"] is True
    assert Decimal(data["estimated_amount"]) == Decimal("260.00")
    assert data["ineligibility_reason"] is None
    assert data["client_type"] == "A"


@pytest.mark.asyncio
async def test_calculate_ineligible_assets(client: AsyncClient):
    """POST /eligibility-estimator/calculate returns eligible=false when assets exceed limit."""
    response = await client.post(
        "/eligibility-estimator/calculate",
        json={
            "relationship_status": "SINGLE",
            "num_dependants": 0,
            "applicant_pwd": False,
            "spouse_pwd": False,
            "monthly_income": "500.00",
            "spouse_monthly_income": "0.00",
            "primary_vehicle_value": "4000.00",
            "other_vehicle_value": "0.00",
            "other_asset_value": "2000.00",
        },
    )
    assert response.status_code == 200
    data = response.json()
    assert data["eligible"] is False
    assert data["ineligibility_reason"] == "assets_exceed_limit"


@pytest.mark.asyncio
async def test_calculate_no_auth_required(client: AsyncClient):
    """Endpoint is public — no Authorization header required."""
    response = await client.post(
        "/eligibility-estimator/calculate",
        json={
            "relationship_status": "SINGLE",
            "num_dependants": 0,
            "applicant_pwd": False,
            "spouse_pwd": False,
            "monthly_income": "0.00",
            "spouse_monthly_income": "0.00",
            "primary_vehicle_value": "0.00",
            "other_vehicle_value": "0.00",
            "other_asset_value": "0.00",
        },
    )
    # Must not return 401 or 403
    assert response.status_code not in (401, 403)


@pytest.mark.asyncio
async def test_calculate_validation_error_negative_income(client: AsyncClient):
    """Pydantic rejects negative monthly_income."""
    response = await client.post(
        "/eligibility-estimator/calculate",
        json={
            "relationship_status": "SINGLE",
            "num_dependants": 0,
            "applicant_pwd": False,
            "spouse_pwd": False,
            "monthly_income": "-100.00",
            "spouse_monthly_income": "0.00",
            "primary_vehicle_value": "0.00",
            "other_vehicle_value": "0.00",
            "other_asset_value": "0.00",
        },
    )
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_calculate_validation_error_spouse_fields_when_single(client: AsyncClient):
    """Pydantic rejects spouse_pwd=True when relationship_status=SINGLE."""
    response = await client.post(
        "/eligibility-estimator/calculate",
        json={
            "relationship_status": "SINGLE",
            "num_dependants": 0,
            "applicant_pwd": False,
            "spouse_pwd": True,
            "monthly_income": "500.00",
            "spouse_monthly_income": "0.00",
            "primary_vehicle_value": "0.00",
            "other_vehicle_value": "0.00",
            "other_asset_value": "0.00",
        },
    )
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_openapi_tags_public(client: AsyncClient):
    """The calculate endpoint appears under the 'public' tag in OpenAPI."""
    response = await client.get("/openapi.json")
    assert response.status_code == 200
    schema = response.json()
    path = schema["paths"].get("/eligibility-estimator/calculate", {})
    post_op = path.get("post", {})
    assert "public" in post_op.get("tags", [])
