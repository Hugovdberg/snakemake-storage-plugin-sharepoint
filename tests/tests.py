__author__ = "Christopher Tomkins-Tinch, Johannes Köster"
__copyright__ = "Copyright 2023, Christopher Tomkins-Tinch, Johannes Köster"
__email__ = "johannes.koester@uni-due.de"
__license__ = "MIT"

from typing import List, Optional, Type
from snakemake_interface_storage_plugins.tests import TestStorageBase
from snakemake_interface_storage_plugins.storage_provider import StorageProviderBase
from snakemake_interface_storage_plugins.settings import StorageProviderSettingsBase
from snakemake_storage_plugin_sharepoint import StorageProvider, StorageProviderSettings


class TestStorageNoSettings(TestStorageBase):
    __test__ = False  # for now no way to test this as we don't have a way to mock the SharePoint server
    retrieve_only = True

    def get_query(self, tmp_path) -> str:
        return "stable"

    def get_query_not_existing(self, tmp_path) -> str:
        return "this/does/not/exist"

    def get_storage_provider_cls(self) -> Type[StorageProviderBase]:
        return StorageProvider

    def get_storage_provider_settings(self) -> Optional[StorageProviderSettingsBase]:
        return StorageProviderSettings(
            site_url="https://snakemake.readthedocs.io", library="en"
        )

    def get_example_args(self) -> List[str]:
        return []
