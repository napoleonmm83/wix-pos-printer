"""
Unit tests for the Wix Printer Service API.
Tests all endpoints for correct behavior, status codes, and response formats.
"""
import pytest
from fastapi.testclient import TestClient
from wix_printer_service.api.main import app

client = TestClient(app)


class TestHealthEndpoint:
    """Test cases for the /health endpoint."""
    
    def test_health_check_success(self):
        """Test that /health endpoint returns 200 status and correct payload."""
        response = client.get("/health")
        
        assert response.status_code == 200
        assert response.json() == {"status": "ok"}
        assert response.headers["content-type"] == "application/json"
    
    def test_health_check_method_not_allowed(self):
        """Test that /health endpoint only accepts GET requests."""
        response = client.post("/health")
        assert response.status_code == 405  # Method Not Allowed
        
        response = client.put("/health")
        assert response.status_code == 405
        
        response = client.delete("/health")
        assert response.status_code == 405


class TestAPIDocumentation:
    """Test cases for API documentation endpoints."""
    
    def test_docs_endpoint_accessible(self):
        """Test that OpenAPI docs are accessible."""
        response = client.get("/docs")
        assert response.status_code == 200
    
    def test_redoc_endpoint_accessible(self):
        """Test that ReDoc documentation is accessible."""
        response = client.get("/redoc")
        assert response.status_code == 200
    
    def test_openapi_json_accessible(self):
        """Test that OpenAPI JSON schema is accessible."""
        response = client.get("/openapi.json")
        assert response.status_code == 200
        assert "application/json" in response.headers["content-type"]
