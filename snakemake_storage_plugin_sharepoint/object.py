"""Definition of the StorageObject for SharePoint."""

import dataclasses
import datetime
import urllib.parse as urlparse
from contextlib import contextmanager
from functools import partial
from typing import TYPE_CHECKING, Any, Generator, Literal, Optional

import requests
from snakemake_interface_common.exceptions import WorkflowError
from snakemake_interface_common.logging import get_logger
from snakemake_interface_storage_plugins.io import IOCacheStorageInterface, Mtime
from snakemake_interface_storage_plugins.storage_object import (
    StorageObjectRead,
    StorageObjectWrite,
)

if TYPE_CHECKING:
    from .provider import StorageProvider as StorageProviderBase
else:
    # Import base class to prevent import cycle since .provider needs to import .object
    from snakemake_interface_storage_plugins.storage_provider import StorageProviderBase

__all__ = ["StorageObject"]

HTTPVerb = Literal["GET", "POST", "HEAD"]
logger = get_logger()


@dataclasses.dataclass
class QueryParseResult:
    library: str
    filepath: str
    overwrite: Optional[bool]


class StorageObject(StorageObjectRead, StorageObjectWrite):
    """Definition of a ReadWritable storage object."""

    DIGEST_URL = "{site_url}/_api/contextinfo"
    GET_FILE_URL = (
        "{site_url}/_api/web/GetFolderByServerRelativeUrl('{folder}')/"
        "Files('{filename}')"
    )
    DOWNLOAD_FILE_URL = (
        "{site_url}/_api/web/GetFolderByServerRelativeUrl('{folder}')/"
        "Files('{filename}')/$value"
    )
    UPLOAD_FILE_URL = (
        "{site_url}/_api/web/GetFolderByServerRelativeUrl('{folder}')/"
        "Files/add(url='{filename}',overwrite={overwrite})"
    )
    if TYPE_CHECKING:
        provider: StorageProviderBase

    def __init__(
        self,
        query: str,
        keep_local: bool,
        retrieve: bool,
        provider: StorageProviderBase,
    ):
        """Initialize the StorageObject and set type hints for custom attributes."""
        self.allow_overwrite: bool
        self.site_url: str
        self.site_netloc: str
        self.library: str
        self.filepath: str
        super().__init__(query, keep_local, retrieve, provider)

    def __post_init__(self):
        """Populate the attributes defined in __init__."""
        if (site_url := self.provider.settings.site_url) is None:
            raise WorkflowError("No site URL specified")
        parsed_site = urlparse.urlparse(site_url)
        self.site_url = site_url.rstrip("/")
        self.site_netloc = parsed_site.netloc

        parsed_query = self.parse_query(self.query)
        self.library = parsed_query.library
        self.filepath = parsed_query.filepath
        self.allow_overwrite = self.get_overwrite_state(
            parsed_query.overwrite, self.provider
        )

    @classmethod
    def get_overwrite_state(
        cls, overwrite: Optional[bool], provider: StorageProviderBase
    ) -> bool:
        """Determine whether a file can be overwritten."""
        match provider.settings.allow_overwrite:
            case False:
                allow_overwrite = False
            case True:
                allow_overwrite = overwrite if overwrite is not None else True
            case _:
                allow_overwrite = overwrite if overwrite is not None else False
        return allow_overwrite

    @classmethod
    def parse_query(cls, query: str) -> QueryParseResult:
        """Parse the query string into the necessary components."""
        parsed_query = urlparse.urlparse(query)
        querystring = urlparse.parse_qs(parsed_query.query, keep_blank_values=True)
        overwrite_string = querystring.get("overwrite", ["none"])[0].lower()
        match overwrite_string:
            case "true":
                overwrite = True
            case "":
                overwrite = True
            case "false":
                overwrite = False
            case "none":
                overwrite = None
            case _:
                raise WorkflowError(f"Invalid overwrite value: {overwrite_string}")
        return QueryParseResult(
            library=parsed_query.netloc,
            filepath=parsed_query.path.lstrip("/"),
            overwrite=overwrite,
        )

    async def inventory(self, cache: IOCacheStorageInterface):
        """From this file, try to find as much information as possible.

        Return as much existence and modification date information as possible.
        Only retrieve that information that comes for free given the current object.
        """
        with self.httpr(self.GET_FILE_URL) as r:
            name = str(self.local_path())
            file_info = FileInfo(r)
            cache.exists_in_storage[name] = file_info.exists()
            cache.mtime[name] = Mtime(storage=file_info.last_modified())
            cache.size[name] = file_info.size()

    def get_inventory_parent(self) -> Optional[str]:
        """Get inventory parent, not implemented for SharePoint."""
        return None

    def cleanup(self):
        """Cleanup the object, not implemented for SharePoint."""
        pass

    def exists(self) -> bool:
        """Determine whether the queried file exists on the server."""
        with self.httpr(self.GET_FILE_URL, "GET") as r:
            return FileInfo(r).exists()

    def mtime(self) -> float:
        """Determine the modification time of the file."""
        with self.httpr(self.GET_FILE_URL, "GET") as r:
            return FileInfo(r).last_modified()

    def size(self) -> int:
        """Determine the size of the file."""
        with self.httpr(self.GET_FILE_URL, "GET") as r:
            return FileInfo(r).size()

    def retrieve_object(self):
        """Copy the file from the server locally."""
        self.local_path().parent.mkdir(parents=True, exist_ok=True)
        with (
            self.httpr(self.DOWNLOAD_FILE_URL, stream=True) as r,
            self.local_path().open("wb") as fh,
        ):
            for chunk in r.iter_content():
                fh.write(chunk)

    # The type: ignore is necessary because the return type is not compatible with the
    # base class:
    # https://github.com/snakemake/snakemake-interface-storage-plugins/pull/48
    def local_suffix(self) -> str:  # type: ignore
        """Get the local filepath relative to the local storage directory."""
        return "/".join([self.site_netloc, self.library, self.filepath])

    def store_object(self):
        """Write the local copy to the server."""
        logger.debug("Getting form digest value")
        with self.httpr(self.DIGEST_URL, "POST") as r:
            try:
                r.raise_for_status()
            except requests.HTTPError as e:
                raise WorkflowError(
                    f"Failed to get form digest value for {self.query}"
                ) from e

            digest_value = r.json()["d"]["GetContextWebInformation"]["FormDigestValue"]

        headers = {"x-requestdigest": digest_value}

        logger.info(f"Uploading {self.query}")
        with open(self.local_path(), "rb") as file:
            with self.httpr(
                self.UPLOAD_FILE_URL, "POST", headers=headers, data=file.read()
            ) as r:
                try:
                    r.raise_for_status()
                except requests.HTTPError as e:
                    en_dis_abled = (
                        "enabled"
                        if self.allow_overwrite
                        else "disabled, allow by adding ?overwrite to the query"
                    )
                    raise WorkflowError(
                        f"Failed to store {self.query} (overwrite is {en_dis_abled})\n"
                        f"Response: {r.status_code} - {r.text}"
                    ) from e

    def remove(self):
        """Remove the file from the SharePoint server.

        Currently not implemented as that would remove file history from the server as
        well.
        """
        logger.debug(f"Removing {self.query} is not implemented.")
        pass

    @contextmanager  # makes this a context manager. after 'yield' is __exit__()
    def httpr(
        self,
        url: str,
        verb: HTTPVerb = "GET",
        stream: bool = False,
        headers: dict[str, str] | None = None,
        data: Optional[Any] = None,
        **kwargs: Any,
    ) -> Generator[requests.Response, Any, None]:
        """Context manager for the connection to the server."""
        _headers = {
            "Content-Type": "application/json; odata=verbose",
            "Accept": "application/json; odata=verbose",
        }
        _url = url.format(
            site_url=self.site_url,
            folder=self.library,
            filename=self.filepath,
            overwrite=str(self.allow_overwrite).lower(),
        )
        logger.debug(f"Requesting HTTP {verb!r} {_url}")
        logger.debug(f"Authenticating with {self.provider.settings.auth}")
        if headers is not None:
            _headers.update(headers)
        r = None
        try:
            match verb.upper():
                case "GET":
                    request = requests.get
                case "POST":
                    request = partial(requests.post, data=data)
                case "HEAD":
                    request = requests.head
                case _:
                    raise NotImplementedError(f"HTTP verb {verb} not implemented")

            r = request(
                _url,
                stream=stream,
                auth=self.provider.settings.auth,
                headers=_headers,
                allow_redirects=self.provider.settings.allow_redirects or True,
                **kwargs,
            )
            logger.debug(f"Response: {r.status_code}")

            yield r
        finally:
            if r is not None:
                r.close()


class FileInfo:
    def __init__(self, response: requests.Response) -> None:
        self.response = response

    def exists(self) -> bool:
        if 300 <= self.response.status_code < 308:
            raise WorkflowError(f"Redirects are not allowed: {self.response.url}")
        return self.response.status_code == requests.codes.ok

    def last_modified(self) -> float:
        if not self.exists():
            return 0
        return datetime.datetime.fromisoformat(
            self.response.json()["d"]["TimeLastModified"]
        ).timestamp()

    def size(self) -> int:
        if not self.exists():
            return 0
        return int(self.response.json()["d"]["Length"])
