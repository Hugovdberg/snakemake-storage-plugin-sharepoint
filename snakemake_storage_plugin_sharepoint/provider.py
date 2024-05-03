# Required:
# Implementation of your storage provider
from typing import TYPE_CHECKING, Any, Iterable, List
from urllib.parse import urlparse

from snakemake_interface_storage_plugins.common import Operation
from snakemake_interface_storage_plugins.storage_provider import (
    ExampleQuery,
    QueryType,
    StorageProviderBase,
    StorageQueryValidationResult,
)

from .object import StorageObject
from .settings import StorageProviderSettings

__all__ = ["StorageProvider", "StorageObject"]


class StorageProvider(StorageProviderBase):
    if TYPE_CHECKING:
        settings: StorageProviderSettings

    def __post_init__(self):
        super().__post_init__()
        if self.settings.site_url is not None:
            self.settings.site_url = self.settings.site_url.rstrip("/")

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
                query="mssp://Documents/data.csv",
                description=(
                    "A file `data.csv` in a SharePoint library called `Documents`."
                ),
                type=QueryType.INPUT,
            ),
            ExampleQuery(
                query="mssp://library/folder/file.txt",
                description=(
                    "A file `file.txt` in a folder named `folder` under a "
                    "SharePoint library called `library`."
                ),
                type=QueryType.INPUT,
            ),
            ExampleQuery(
                query="mssp://Documents/output.csv",
                description=(
                    "A file `target.csv` in a SharePoint library called `Documents`."
                ),
                type=QueryType.OUTPUT,
            ),
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
            parsed = urlparse(query)
            scheme = parsed.scheme
            library = parsed.netloc
            filepath = parsed.path.lstrip("/")
        except Exception as e:
            return StorageQueryValidationResult(
                query=query,
                valid=False,
                reason=f"cannot be parsed as URL ({e})",
            )
        if not scheme == "mssp":
            return StorageQueryValidationResult(
                query=query,
                valid=False,
                reason="scheme must be 'mssp'",
            )
        if library == "":
            return StorageQueryValidationResult(
                query=query,
                valid=False,
                reason="library must be specified (e.g. mssp://library/file.txt)",
            )
        if filepath == "":
            return StorageQueryValidationResult(
                query=query,
                valid=False,
                reason=(
                    "path must specify the library and file path (e.g. "
                    "mssp://library/file.txt or mssp://library/folder/file.txt)"
                ),
            )
        return StorageQueryValidationResult(
            query=query,
            valid=True,
        )

    def list_objects(self, query: Any) -> Iterable[str]:
        raise NotImplementedError()
