"""Tests for the Mergington High School Management System API."""

import copy

import pytest
from fastapi.testclient import TestClient

from src.app import activities, app

client = TestClient(app)


@pytest.fixture(autouse=True)
def reset_activities():
    """Snapshot and restore the in-memory `activities` dict around each test.

    The app stores all state in a single module-level dict that signup/unregister
    mutate in place, so tests must restore it to avoid leaking state between tests.
    """
    original = copy.deepcopy(activities)
    yield
    activities.clear()
    activities.update(original)


def test_root_redirects_to_static_index():
    response = client.get("/", follow_redirects=False)

    assert response.status_code in (307, 308)
    assert response.headers["location"] == "/static/index.html"


def test_get_activities_returns_seeded_data():
    response = client.get("/activities")

    assert response.status_code == 200
    data = response.json()
    assert "Chess Club" in data
    chess_club = data["Chess Club"]
    assert set(["description", "schedule", "max_participants", "participants"]) <= set(chess_club)
    assert "michael@mergington.edu" in chess_club["participants"]


def test_signup_for_activity_success():
    email = "newstudent@mergington.edu"

    response = client.post("/activities/Chess Club/signup", params={"email": email})

    assert response.status_code == 200
    assert response.json() == {"message": f"Signed up {email} for Chess Club"}
    assert email in activities["Chess Club"]["participants"]


def test_signup_for_activity_duplicate_returns_400():
    email = "michael@mergington.edu"  # already signed up in seed data

    response = client.post("/activities/Chess Club/signup", params={"email": email})

    assert response.status_code == 400
    assert response.json() == {"detail": "Student is already signed up for this activity"}


def test_signup_for_unknown_activity_returns_404():
    response = client.post(
        "/activities/Not A Real Club/signup",
        params={"email": "someone@mergington.edu"},
    )

    assert response.status_code == 404
    assert response.json() == {"detail": "Activity not found"}


def test_unregister_from_activity_success():
    email = "michael@mergington.edu"  # already signed up in seed data

    response = client.delete("/activities/Chess Club/unregister", params={"email": email})

    assert response.status_code == 200
    assert response.json() == {"message": f"Unregistered {email} from Chess Club"}
    assert email not in activities["Chess Club"]["participants"]


def test_unregister_not_signed_up_returns_400():
    email = "notsignedup@mergington.edu"

    response = client.delete("/activities/Chess Club/unregister", params={"email": email})

    assert response.status_code == 400
    assert response.json() == {"detail": "Student is not signed up for this activity"}


def test_unregister_from_unknown_activity_returns_404():
    response = client.delete(
        "/activities/Not A Real Club/unregister",
        params={"email": "someone@mergington.edu"},
    )

    assert response.status_code == 404
    assert response.json() == {"detail": "Activity not found"}


def test_signup_beyond_max_participants_is_not_currently_enforced():
    """Documents current behavior: the API does not enforce `max_participants` on signup.

    This is not a desired behavior assertion, just a record of the existing gap so a
    future capacity check can be tested against this case.
    """
    activity_name = "Chess Club"
    activity = activities[activity_name]
    max_participants = activity["max_participants"]

    # Fill the activity up to capacity with new emails.
    while len(activity["participants"]) < max_participants:
        filler_email = f"filler{len(activity['participants'])}@mergington.edu"
        client.post(f"/activities/{activity_name}/signup", params={"email": filler_email})

    # One more signup beyond capacity currently still succeeds (no capacity check).
    response = client.post(
        f"/activities/{activity_name}/signup",
        params={"email": "overcapacity@mergington.edu"},
    )

    assert response.status_code == 200
    assert len(activity["participants"]) == max_participants + 1
