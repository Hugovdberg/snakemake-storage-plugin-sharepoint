__author__ = "Hugo Lapre"
__copyright__ = "Copyright 2024, Hugo Lapre"
__email__ = "github@tbdwebdesign.nl"
__license__ = "MIT"

from contextlib import contextmanager
from dataclasses import dataclass, field
from functools import partial
from typing import TYPE_CHECKING, Any, Iterable, List, Optional
from urllib.parse import urlparse

import requests
import snakemake_storage_plugin_http as http
from snakemake_interface_common.exceptions import WorkflowError
from snakemake_interface_storage_plugins.common import Operation
from snakemake_interface_storage_plugins.storage_object import StorageObjectWrite
from snakemake_interface_storage_plugins.storage_provider import (
    ExampleQuery,
    QueryType,
    StorageQueryValidationResult,
)


# Define settings for your storage plugin (e.g. host url, credentials).
# They will occur in the Snakemake CLI as --storage-<storage-plugin-name>-<param-name>
# Make sure that all defined fields are 'Optional' and specify a default value
# of None or anything else that makes sense in your case.
# Note that we allow storage plugin settings to be tagged by the user. That means,
# that each of them can be specified multiple times (an implicit nargs=+), and
# the user can add a tag in front of each value (e.g. tagname1:value1 tagname2:value2).
# This way, a storage plugin can be used multiple times within a workflow with different
# settings.
@dataclass
class StorageProviderSettings(http.StorageProviderSettings):
    site_url: Optional[str] = field(
        default=None,
        metadata={
            "help": "The URL of the SharePoint site.",
            "env_var": True,
        },
    )
    library: Optional[str] = field(
        default=None,
        metadata={
            "help": "The folder in the SharePoint site to work with.",
        },
    )
    allow_overwrite: bool = field(
        default=False,
        metadata={
            "help": "Allow overwriting files in the SharePoint site.",
        },
    )


# Required:
# Implementation of your storage provider
class StorageProvider(http.StorageProvider):
    if TYPE_CHECKING:
        settings: StorageProviderSettings

    def __post_init__(self):
        super().__post_init__()
        if self.settings.site_url is None:
            raise WorkflowError("No SharePoint site URL provided.")
        else:
            self.settings.site_url = self.settings.site_url.rstrip("/")
        if self.settings.library is None:
            raise WorkflowError("No SharePoint folder provided.")
        else:
            self.settings.library = self.settings.library.strip("/")

    def rate_limiter_key(self, query: str, operation: Operation) -> Any:
        """Return a key for identifying a rate limiter given a query and an operation.

        This is used to identify a rate limiter for the query.
        E.g. for a storage provider like http that would be the host name.
        For s3 it might be just the endpoint URL.
        """
        parsed = urlparse(self.settings.site_url)
        return parsed.netloc

    @classmethod
    def example_queries(cls) -> List[ExampleQuery]:
        """Return an example query with description for this storage provider."""
        return [
            ExampleQuery(
                query="file.txt",
                description="A file URL",
                type=QueryType.INPUT,
            )
        ]

    def default_max_requests_per_second(self) -> float:
        """Return the default maximum number of requests per second for this storage
        provider."""
        return 10.0

    def use_rate_limiter(self) -> bool:
        """Return False if no rate limiting is needed for this provider."""
        return True

    @classmethod
    def is_valid_query(cls, query: str) -> StorageQueryValidationResult:
        try:
            urlparse(f"http://example.com/{query}")
        except Exception as e:
            return StorageQueryValidationResult(
                query=query,
                valid=False,
                reason=f"cannot be parsed as URL ({e})",
            )
        return StorageQueryValidationResult(
            query=query,
            valid=True,
        )

    def list_objects(self, query: Any) -> Iterable[str]:
        raise NotImplementedError()


# Required:
# Implementation of storage object (also check out
# snakemake_interface_storage_plugins.storage_object for more base class options)
class StorageObject(http.StorageObject, StorageObjectWrite):
    if TYPE_CHECKING:
        provider: StorageProvider

    @property
    def full_query(self):
        return "/".join(  # type: ignore
            [
                self.provider.settings.site_url,  # type: ignore
                self.provider.settings.library,  # type: ignore
                self.query,
            ]
        )

    def local_suffix(self):
        parsed = urlparse(self.full_query)
        return f"{parsed.netloc}/{parsed.path}"

    def store_object(self):
        site_url = self.provider.settings.site_url
        folder = self.provider.settings.library
        filename = self.query

        overwrite = self.provider.settings.allow_overwrite

        digest_url = f"{site_url}/_api/contextinfo"
        request_url = (
            f"{site_url}/_api/web/getfolderbyserverrelativeurl('{folder}')/"
            f"Files/add(url='{filename}',overwrite={str(overwrite).lower()})"
        )

        headers = {
            "Content-Type": "application/json; odata=verbose",
            "Accept": "application/json; odata=verbose",
        }

        r = requests.post(
            digest_url,
            auth=self.provider.settings.auth,
            headers=headers,
            timeout=1000,
        )
        r.raise_for_status()
        digest_value = r.json()["d"]["GetContextWebInformation"]["FormDigestValue"]
        headers.update({"x-requestdigest": digest_value})

        with open(self.local_path(), "rb") as file:
            upload_result = requests.post(
                request_url,
                timeout=1000,
                auth=self.provider.settings.auth,
                headers=headers,
                data=file.read(),
            )
            upload_result.raise_for_status()

    def remove(self):
        pass

    @contextmanager  # makes this a context manager. after 'yield' is __exit__()
    def httpr(self, verb="GET", stream=False):
        r = None
        try:
            match verb.upper():
                case "GET":
                    request = partial(requests.get, stream=stream)
                case "POST":
                    request = partial(requests.post, stream=stream)
                case "HEAD":
                    request = requests.head
                case _:
                    raise NotImplementedError(f"HTTP verb {verb} not implemented")

            r = request(
                self.full_query,
                stream=stream,
                auth=self.provider.settings.auth,
                allow_redirects=self.provider.settings.allow_redirects or False,
            )

            yield r
        finally:
            if r is not None:
                r.close()
