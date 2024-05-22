__author__ = "Christopher Tomkins-Tinch, Johannes Köster"
__copyright__ = "Copyright 2023, Christopher Tomkins-Tinch, Johannes Köster"
__email__ = "johannes.koester@uni-due.de"
__license__ = "MIT"

import contextlib
import pathlib
import tempfile
from typing import Generator, List, Optional, Type

import pytest
from snakemake_interface_storage_plugins.settings import StorageProviderSettingsBase
from snakemake_interface_storage_plugins.storage_provider import StorageProviderBase
from snakemake_interface_storage_plugins.tests import TestStorageBase

from snakemake_storage_plugin_sharepoint import (
    StorageObject,
    StorageProvider,
    StorageProviderSettings,
)


class TestStorageNoSettings(TestStorageBase):
    # For now there is no way to test this package as we don't have a way to mock a
    # SharePoint server, therefore we set __test__ to False
    __test__ = False

    def get_query(self, tmp_path) -> str:
        return "mssp://en/stable"

    def get_query_not_existing(self, tmp_path) -> str:
        return "mssp://this/does/not/exist"

    def get_storage_provider_cls(self) -> Type[StorageProviderBase]:
        return StorageProvider

    def get_storage_provider_settings(self) -> Optional[StorageProviderSettingsBase]:
        return StorageProviderSettings(site_url="https://snakemake.readthedocs.io")

    def get_example_args(self) -> List[str]:
        return []


def query_is_valid(query: str) -> bool:
    return StorageProvider.is_valid_query(query).valid


def query_is_invalid(query: str) -> bool:
    return not query_is_valid(query)


class TestQueryValidation:
    def test_query_with_library_and_filename_is_valid(self):
        assert query_is_valid("mssp://library/filename.txt")

    def test_query_with_library_and_folder_and_filename_is_valid(self):
        assert query_is_valid("mssp://library/folder/filename.txt")

    def test_empty_query_is_invalid(self):
        assert query_is_invalid("")

    def test_query_with_no_library_and_no_filename_is_invalid(self):
        assert query_is_invalid("mssp://")

    def test_query_with_library_and_no_filename_is_invalid(self):
        assert query_is_invalid("mssp://library/")

    def test_query_with_no_library_is_invalid(self):
        assert query_is_invalid("mssp://filename.txt")

    def test_query_with_no_schema_invalid(self):
        assert query_is_invalid("library/filename.txt")

    def test_query_with_fragments_is_invalid(self):
        assert query_is_invalid("mssp://library/filename.txt#fragment")

    def test_query_with_overwrite_set_to_true_is_valid(self):
        assert query_is_valid("mssp://library/filename.txt?overwrite=true")

    def test_query_with_overwrite_set_to_empty_is_valid(self):
        assert query_is_valid("mssp://library/filename.txt?overwrite")

    def test_query_with_overwrite_set_to_false_is_valid(self):
        assert query_is_valid("mssp://library/filename.txt?overwrite=false")

    def test_query_with_overwrite_set_to_invalid_is_invalid(self):
        assert query_is_invalid("mssp://library/filename.txt?overwrite=invalid")

    def test_query_with_invalid_option_is_invalid(self):
        assert query_is_invalid("mssp://library/filename.txt?invalid=true")


@contextlib.contextmanager
def storage_provider(
    allow_overwrite: Optional[bool] = None,
) -> Generator[StorageProvider, None, None]:
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
    def test_overwrite_state_setting_default_and_file_default_is_false(self):
        with storage_provider(allow_overwrite=None) as provider:
            assert not StorageObject.get_overwrite_state(None, provider)

    def test_overwrite_state_setting_default_and_file_true_is_true(self):
        with storage_provider(allow_overwrite=None) as provider:
            assert StorageObject.get_overwrite_state(True, provider)

    def test_overwrite_state_setting_default_and_file_false_is_false(self):
        with storage_provider(allow_overwrite=None) as provider:
            assert not StorageObject.get_overwrite_state(False, provider)

    def test_overwrite_state_setting_true_and_file_default_is_true(self):
        with storage_provider(allow_overwrite=True) as provider:
            assert StorageObject.get_overwrite_state(None, provider)

    def test_overwrite_state_setting_true_and_file_true_is_true(self):
        with storage_provider(allow_overwrite=True) as provider:
            assert StorageObject.get_overwrite_state(True, provider)

    def test_overwrite_state_setting_true_and_file_false_is_false(self):
        with storage_provider(allow_overwrite=True) as provider:
            assert not StorageObject.get_overwrite_state(False, provider)

    def test_overwrite_state_setting_false_and_file_default_is_false(self):
        with storage_provider(allow_overwrite=False) as provider:
            assert not StorageObject.get_overwrite_state(None, provider)

    def test_overwrite_state_setting_false_and_file_true_is_false(self):
        with storage_provider(allow_overwrite=False) as provider:
            assert not StorageObject.get_overwrite_state(True, provider)

    def test_overwrite_state_setting_false_and_file_false_is_false(self):
        with storage_provider(allow_overwrite=False) as provider:
            assert not StorageObject.get_overwrite_state(False, provider)
