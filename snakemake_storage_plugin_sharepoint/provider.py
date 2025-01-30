"""Implementation of the storage provider protocol."""

import urllib.parse as urlparse
from typing import TYPE_CHECKING, Any, Iterable, List

from snakemake_interface_common.logging import get_logger
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
logger = get_logger()


class StorageProvider(StorageProviderBase):
    """Implementation of the storage provider protocol."""

    if TYPE_CHECKING:
        settings: StorageProviderSettings

    def __post_init__(self):
        """Post-initialize local fields."""
        super().__post_init__()
        if self.settings.site_url is not None:
            self.settings.site_url = self.settings.site_url.rstrip("/")

    def rate_limiter_key(self, query: str, operation: Operation) -> Any:
        """Return a key for identifying a rate limiter given a query and an operation.

        This is used to identify a rate limiter for the query.
        E.g. for a storage provider like http that would be the host name.
        For s3 it might be just the endpoint URL.
        """
        parsed = urlparse.urlparse(self.settings.site_url)
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
                    "A file `file.txt` under a folder named `folder` in a "
                    "SharePoint library called `library`."
                ),
                type=QueryType.INPUT,
            ),
            ExampleQuery(
                query="mssp://Documents/target.csv",
                description=(
                    "A file `target.csv` in a SharePoint library called `Documents`. "
                    "Overwrite behavior determined by the `allow_overwrite` setting."
                ),
                type=QueryType.OUTPUT,
            ),
            ExampleQuery(
                query="mssp://library/folder/file.txt?overwrite",
                description=(
                    "A file `file.txt` under a folder named `folder` in a "
                    "SharePoint library called `library`. Overwrite allowed"
                    "if the `allow_overwrite` setting is not False."
                ),
                type=QueryType.OUTPUT,
            ),
        ]

    def default_max_requests_per_second(self) -> float:
        """Return the default maximum number of requests per second."""
        return 10.0

    def use_rate_limiter(self) -> bool:
        """Return False if no rate limiting is needed for this provider."""
        return True

    @classmethod
    def is_valid_query(cls, query: str) -> StorageQueryValidationResult:
        """Determine whether the query is valid."""
        try:
            parsed = urlparse.urlparse(query)
        except Exception as e:
            return StorageQueryValidationResult(
                query=query,
                valid=False,
                reason=f"cannot be parsed as URL ({e})",
            )
        logger.debug(f"parsed query: {parsed!r}")
        scheme = parsed.scheme
        library = parsed.netloc
        filepath = parsed.path.lstrip("/")
        querystring = parsed.query
        fragment = parsed.fragment
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
        if querystring:
            result = cls._validate_querystring(query, querystring)
            logger.debug(f"querystring validation result: {result!r}")
            if result is not None:
                return result
        if fragment:
            return StorageQueryValidationResult(
                query=query,
                valid=False,
                reason="fragment is not allowed",
            )
        return StorageQueryValidationResult(
            query=query,
            valid=True,
        )

    @classmethod
    def _validate_querystring(
        cls, query: str, querystring: str
    ) -> StorageQueryValidationResult | None:
        query_params = urlparse.parse_qs(querystring, keep_blank_values=True)
        logger.debug(f"query parameters: {query_params!r}")
        valid_keys = {"overwrite"}
        invalid_keys = set(query_params.keys()) - valid_keys
        logger.debug(f"invalid keys: {invalid_keys!r}")
        if invalid_keys:
            return StorageQueryValidationResult(
                query=query,
                valid=False,
                reason=f"invalid query parameters: {', '.join(invalid_keys)}",
            )
        for option in query_params:
            if len(query_params[option]) != 1:
                return StorageQueryValidationResult(
                    query=query,
                    valid=False,
                    reason=f"{option} must be specified exactly once",
                )
        if "overwrite" in query_params:
            overwrite = query_params["overwrite"][0].lower() or "true"
            if overwrite not in {"true", "false", "none", ""}:
                return StorageQueryValidationResult(
                    query=query,
                    valid=False,
                    reason="overwrite must be 'true', 'false', 'none', or empty",
                )
        return

    def list_objects(self, query: Any) -> Iterable[str]:
        """Return a list of available storage objects from the server."""
        raise NotImplementedError()
