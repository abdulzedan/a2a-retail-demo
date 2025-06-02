"""
Pytest configuration and shared fixtures for A2A retail demo tests.
"""

import pytest
import asyncio
from unittest.mock import Mock, AsyncMock
import os
import sys

# Add the backend directory to the Python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

# Set dummy environment variables for testing (will be mocked anyway)
os.environ.setdefault(
    "VERTEX_SEARCH_SERVING_CONFIG", "projects/test/locations/test/collections/test/dataStores/test/servingConfigs/test"
)
os.environ.setdefault("GOOGLE_API_KEY", "test-key-not-used")


@pytest.fixture(scope="session")
def event_loop():
    """Create an instance of the default event loop for the test session."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture
def mock_vector_store():
    """Mock VertexSearchStore for testing."""
    store = Mock()

    # Mock search results
    store.search = Mock(
        return_value=[
            {
                "id": "PROD-001",
                "name": "Smart TV 55-inch 4K",
                "description": "Ultra HD Smart LED TV with built-in streaming",
                "price": 699.99,
                "category": "Electronics",
                "brand": "TechVision",
                "stock_quantity": 15,
                "stock_status": "in_stock",
                "sku": "TV-55-4K-001",
            },
            {
                "id": "PROD-002",
                "name": "Smart TV 65-inch OLED",
                "description": "Premium OLED Smart TV with HDR",
                "price": 1299.99,
                "category": "Electronics",
                "brand": "TechVision",
                "stock_quantity": 8,
                "stock_status": "in_stock",
                "sku": "TV-65-OLED-001",
            },
        ]
    )

    # Mock get_by_id
    def mock_get_by_id(product_id: str):
        products = {
            "PROD-001": {
                "id": "PROD-001",
                "name": "Smart TV 55-inch 4K",
                "price": 699.99,
                "stock_quantity": 15,
                "stock_status": "in_stock",
            },
            "PROD-999": None,  # Non-existent product
        }
        return products.get(product_id)

    store.get_by_id = Mock(side_effect=mock_get_by_id)

    return store


@pytest.fixture
def mock_agent_runner():
    """Mock agent runner for ADK agents."""
    runner = Mock()

    # Create async generator for run_async
    async def mock_run_async(*_args, **_kwargs):  # Args intentionally unused in mock
        # Yield a mock event with content
        mock_event = Mock()
        mock_event.content = Mock()
        mock_event.content.parts = []
        mock_event.is_final_response = Mock(return_value=True)
        mock_event.content.text = "Here are the products I found."
        yield mock_event

    runner.run_async = mock_run_async
    return runner


@pytest.fixture
def mock_gemini_model():
    """Mock Gemini model for testing."""
    model = Mock()

    # Mock response
    mock_response = Mock()
    mock_response.candidates = [Mock()]
    mock_response.candidates[0].content = Mock()
    mock_response.candidates[0].content.parts = [Mock()]
    mock_response.candidates[0].content.parts[0].text = "I'll help you find products."

    model.generate_content_async = AsyncMock(return_value=mock_response)

    return model


@pytest.fixture
def sample_products():
    """Sample product data for testing."""
    return [
        {
            "id": "PROD-001",
            "name": "Wireless Headphones",
            "description": "Bluetooth noise-cancelling headphones",
            "price": 199.99,
            "category": "Electronics",
            "brand": "AudioTech",
            "stock_quantity": 50,
            "stock_status": "in_stock",
        },
        {
            "id": "PROD-002",
            "name": "Smart Watch",
            "description": "Fitness tracking smartwatch with heart rate monitor",
            "price": 299.99,
            "category": "Electronics",
            "brand": "TechWear",
            "stock_quantity": 0,
            "stock_status": "out_of_stock",
        },
        {
            "id": "PROD-003",
            "name": "Coffee Maker",
            "description": "Programmable coffee maker with thermal carafe",
            "price": 89.99,
            "category": "Appliances",
            "brand": "BrewMaster",
            "stock_quantity": 25,
            "stock_status": "in_stock",
        },
    ]


@pytest.fixture
def mock_a2a_response():
    """Mock A2A protocol response."""
    return {
        "response": "Product found successfully",
        "metadata": {"agent": "inventory", "timestamp": "2024-01-01T00:00:00Z"},
    }


@pytest.fixture
def mock_httpx_client():
    """Mock httpx client for A2A communication."""
    client = Mock()
    response = Mock()
    response.status_code = 200
    response.json = Mock(return_value={"response": "Success", "data": {"products": []}})
    response.text = '{"response": "Success"}'

    client.post = AsyncMock(return_value=response)
    return client
