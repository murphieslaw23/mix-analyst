"""Unit coverage for bearer-derived native media capabilities."""

import pytest

from api.app.schemas.auth import CurrentPrincipal
from api.app.services.auth import (
    ARTIFACT_TICKET_MAX_TTL_SECONDS,
    ARTIFACT_TICKET_MIN_TTL_SECONDS,
    artifact_ticket_ttl,
    decode_artifact_ticket,
    issue_artifact_ticket,
)


def test_artifact_ticket_round_trip_is_bound_to_exact_mix_and_artifact():
    principal = CurrentPrincipal(user_id="user-a", project_id="project-a")
    ticket = issue_artifact_ticket(principal, "mix-a", "artifact-a", ttl_seconds=600)

    decoded = decode_artifact_ticket(ticket, "mix-a", "artifact-a")
    assert decoded.user_id == "user-a"
    assert decoded.project_id == "project-a"

    with pytest.raises(ValueError):
        decode_artifact_ticket(ticket, "mix-b", "artifact-a")
    with pytest.raises(ValueError):
        decode_artifact_ticket(ticket, "mix-a", "artifact-b")


def test_artifact_ticket_lifetime_covers_long_form_listen_but_is_capped():
    assert artifact_ticket_ttl(60.0) == ARTIFACT_TICKET_MIN_TTL_SECONDS
    assert artifact_ticket_ttl(3 * 60 * 60) == (3 * 60 * 60) + (15 * 60)
    assert artifact_ticket_ttl(24 * 60 * 60) == ARTIFACT_TICKET_MAX_TTL_SECONDS
