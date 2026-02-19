"""Fake connectors for integration testing."""

from tests.integration.fakes.azure_fake import FakeAzureConnector
from tests.integration.fakes.gcp_fake import FakeGCPConnector

__all__ = ["FakeAzureConnector", "FakeGCPConnector"]
