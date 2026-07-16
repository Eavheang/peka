from fastapi.testclient import TestClient


def test_create_and_list_todos(client: TestClient) -> None:
    created = client.post("/todos", json={"title": "Buy milk"})

    assert created.status_code == 201
    assert created.json()["title"] == "Buy milk"
    assert created.json()["completed"] is False

    listed = client.get("/todos")
    assert listed.status_code == 200
    assert listed.json()[0]["title"] == "Buy milk"


def test_update_and_delete_todo(client: TestClient) -> None:
    todo_id = client.post("/todos", json={"title": "Read book"}).json()["id"]

    updated = client.patch(f"/todos/{todo_id}", json={"completed": True})
    assert updated.status_code == 200
    assert updated.json()["completed"] is True

    deleted = client.delete(f"/todos/{todo_id}")
    assert deleted.status_code == 204
    assert client.patch(f"/todos/{todo_id}", json={"completed": False}).status_code == 404


def test_todo_validation_and_not_found(client: TestClient) -> None:
    assert client.post("/todos", json={"title": ""}).status_code == 422
    assert client.patch("/todos/99999", json={"completed": True}).status_code == 404
