"""Tests for the SharePoint storage provider.

Note that the actual connections are not tested in this suite as that would necessitate
mocking an entire SharePoint server.
"""

__author__ = "Christopher Tomkins-Tinch, Johannes Köster"
__copyright__ = "Copyright 2023, Christopher Tomkins-Tinch, Johannes Köster"
__email__ = "johannes.koester@uni-due.de"
__license__ = "MIT"

import contextlib
import pathlib
import tempfile
from typing import Generator, List, Optional, Type

from snakemake_interface_storage_plugins.settings import StorageProviderSettingsBase
from snakemake_interface_storage_plugins.storage_provider import StorageProviderBase
from snakemake_interface_storage_plugins.tests import TestStorageBase

from snakemake_storage_plugin_sharepoint import (
    StorageObject,
    StorageProvider,
    StorageProviderSettings,
)


class TestStorageNoSettings(TestStorageBase):
    """Test the storage plugin without settings.

    For now there is no way to test this package as we don't have a way to mock a
    SharePoint server, therefore we set __test__ to False.
    """

    __test__ = False

    def get_query(self, tmp_path) -> str:
        """Return a valid query."""
        return "mssp://en/stable"

    def get_query_not_existing(self, tmp_path) -> str:
        """Return a invalid query."""
        return "mssp://this/does/not/exist"

    def get_storage_provider_cls(self) -> Type[StorageProviderBase]:
        """Return a storage provider."""
        return StorageProvider

    def get_storage_provider_settings(self) -> Optional[StorageProviderSettingsBase]:
        """Return a storage provider settings object."""
        return StorageProviderSettings(site_url="https://snakemake.readthedocs.io")

    def get_example_args(self) -> List[str]:
        """Return an example of arguments."""
        return []


def query_is_valid(query: str) -> bool:
    """Return True if the query is valid."""
    return StorageProvider.is_valid_query(query).valid


def query_is_invalid(query: str) -> bool:
    """Return True if the query is invalid."""
    return not query_is_valid(query)


class TestQueryValidation:
    """Test the query schema validation."""

    def test_query_with_library_and_filename_is_valid(self):
        """Test query with library and filename is valid."""
        assert query_is_valid("mssp://library/filename.txt")

    def test_query_with_library_and_folder_and_filename_is_valid(self):
        """Test query with library and folder and filename is valid."""
        assert query_is_valid("mssp://library/folder/filename.txt")

    def test_empty_query_is_invalid(self):
        """Test empty query is invalid."""
        assert query_is_invalid("")

    def test_query_with_no_library_and_no_filename_is_invalid(self):
        """Test query with no library and no filename is invalid."""
        assert query_is_invalid("mssp://")

    def test_query_with_library_and_no_filename_is_invalid(self):
        """Test query with library and no filename is invalid."""
        assert query_is_invalid("mssp://library/")

    def test_query_with_no_library_is_invalid(self):
        """Test query with no library is invalid."""
        assert query_is_invalid("mssp://filename.txt")

    def test_query_with_no_schema_invalid(self):
        """Test query with no schema invalid."""
        assert query_is_invalid("library/filename.txt")

    def test_query_with_fragments_is_invalid(self):
        """Test query with fragments is invalid."""
        assert query_is_invalid("mssp://library/filename.txt#fragment")

    def test_query_with_overwrite_set_to_true_is_valid(self):
        """Test query with overwrite set to true is valid."""
        assert query_is_valid("mssp://library/filename.txt?overwrite=true")

    def test_query_with_overwrite_set_to_empty_is_valid(self):
        """Test query with overwrite set to empty is valid."""
        assert query_is_valid("mssp://library/filename.txt?overwrite")

    def test_query_with_overwrite_set_to_false_is_valid(self):
        """Test query with overwrite set to false is valid."""
        assert query_is_valid("mssp://library/filename.txt?overwrite=false")

    def test_query_with_overwrite_set_to_invalid_is_invalid(self):
        """Test query with overwrite set to invalid is invalid."""
        assert query_is_invalid("mssp://library/filename.txt?overwrite=invalid")

    def test_query_with_invalid_option_is_invalid(self):
        """Test query with invalid option is invalid."""
        assert query_is_invalid("mssp://library/filename.txt?invalid=true")


@contextlib.contextmanager
def storage_provider(
    allow_overwrite: Optional[bool] = None,
) -> Generator[StorageProvider, None, None]:
    """Return a storage provider with settings."""
    settings = StorageProviderSettings(
        site_url="https://snakemake.readthedocs.io", allow_overwrite=allow_overwrite
    )
    try:
        with tempfile.TemporaryDirectory() as tempdir:
            path = pathlib.Path(tempdir)
            yield StorageProvider(local_prefix=path, settings=settings)
    finally:
        pass


class TestOverwriteState:
    """Test the detection of the allow_overwrite state."""

    def test_overwrite_state_setting_default_and_file_default_is_false(self):
        """Test overwrite state setting default and file default is false."""
        with storage_provider(allow_overwrite=None) as provider:
            assert not StorageObject.get_overwrite_state(None, provider)

    def test_overwrite_state_setting_default_and_file_true_is_true(self):
        """Test overwrite state setting default and file true is true."""
        with storage_provider(allow_overwrite=None) as provider:
            assert StorageObject.get_overwrite_state(True, provider)

    def test_overwrite_state_setting_default_and_file_false_is_false(self):
        """Test overwrite state setting default and file false is false."""
        with storage_provider(allow_overwrite=None) as provider:
            assert not StorageObject.get_overwrite_state(False, provider)

    def test_overwrite_state_setting_true_and_file_default_is_true(self):
        """Test overwrite state setting true and file default is true."""
        with storage_provider(allow_overwrite=True) as provider:
            assert StorageObject.get_overwrite_state(None, provider)

    def test_overwrite_state_setting_true_and_file_true_is_true(self):
        """Test overwrite state setting true and file true is true."""
        with storage_provider(allow_overwrite=True) as provider:
            assert StorageObject.get_overwrite_state(True, provider)

    def test_overwrite_state_setting_true_and_file_false_is_false(self):
        """Test overwrite state setting true and file false is false."""
        with storage_provider(allow_overwrite=True) as provider:
            assert not StorageObject.get_overwrite_state(False, provider)

    def test_overwrite_state_setting_false_and_file_default_is_false(self):
        """Test overwrite state setting false and file default is false."""
        with storage_provider(allow_overwrite=False) as provider:
            assert not StorageObject.get_overwrite_state(None, provider)

    def test_overwrite_state_setting_false_and_file_true_is_false(self):
        """Test overwrite state setting false and file true is false."""
        with storage_provider(allow_overwrite=False) as provider:
            assert not StorageObject.get_overwrite_state(True, provider)

    def test_overwrite_state_setting_false_and_file_false_is_false(self):
        """Test overwrite state setting false and file false is false."""
        with storage_provider(allow_overwrite=False) as provider:
            assert not StorageObject.get_overwrite_state(False, provider)
