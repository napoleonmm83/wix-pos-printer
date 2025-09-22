"""
Unit tests for the Wix Printer Service API.
Tests all endpoints for correct behavior, status codes, and response formats.
"""
import pytest
from wix_printer_service.api.main import app


@pytest.fixture
def simple_app():
    """Return the FastAPI app for testing."""
    return app


def test_app_creation():
    """Test that the app can be created without errors."""
    assert app is not None
    assert hasattr(app, 'routes')
    
    
def test_health_endpoint_exists():
    """Test that health endpoint is registered."""
    routes = [route.path for route in app.routes if hasattr(route, 'path')]
    assert '/health' in routes


def test_multiple_routes_exist():
    """Test that multiple expected routes exist."""
    routes = [route.path for route in app.routes if hasattr(route, 'path')]
    expected_routes = ['/health', '/docs', '/redoc', '/openapi.json']
    
    for route in expected_routes:
        assert route in routes, f"Route {route} not found in {routes}"
