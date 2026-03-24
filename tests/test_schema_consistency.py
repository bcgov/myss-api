from app.models.service_requests import SRDraft


def test_srdraft_model_matches_sr_drafts_table():
    assert SRDraft.__tablename__ == "sr_drafts"
    columns = {c.name for c in SRDraft.__table__.columns}
    assert "sr_id" in columns
    assert "user_id" in columns
    assert "sr_type" in columns
    assert "draft_json" in columns
    assert "updated_at" in columns
