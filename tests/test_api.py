import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch
from scripts.api import app

client = TestClient(app)

def test_health_check():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "service": "retail-intelligence-api"}

def test_tools_endpoint():
    response = client.get("/tools")
    assert response.status_code == 200
    assert len(response.json()["tools"]) == 2

# We mock the LangChain agent so we don't spend Azure tokens during CI
@patch("scripts.api.ask")
def test_ask_endpoint(mock_ask):
    mock_ask.return_value = "Migros had the highest revenue."
    
    payload = {"question": "Who had the highest revenue?"}
    response = client.post("/ask", json=payload)
    
    assert response.status_code == 200
    data = response.json()
    assert data["answer"] == "Migros had the highest revenue."
    assert data["model"] == "gpt-4o"
    mock_ask.assert_called_once_with("Who had the highest revenue?")