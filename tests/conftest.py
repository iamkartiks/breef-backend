"""Pytest configuration and fixtures."""
import pytest
from shared.database import Database


@pytest.fixture
def db():
    """Database fixture."""
    return Database()


@pytest.fixture
def mock_supabase_client(monkeypatch):
    """Mock Supabase client."""
    class MockClient:
        def table(self, name):
            return self
        
        def select(self, *args):
            return self
        
        def insert(self, data):
            return self
        
        def update(self, data):
            return self
        
        def eq(self, key, value):
            return self
        
        def execute(self):
            class MockResponse:
                data = []
            return MockResponse()
    
    monkeypatch.setattr("shared.database.create_client", lambda *args: MockClient())
    return MockClient()

