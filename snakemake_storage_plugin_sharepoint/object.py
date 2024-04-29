# Required:
# Implementation of storage object (also check out
# snakemake_interface_storage_plugins.storage_object for more base class options)
import datetime
from contextlib import contextmanager
from functools import partial
from typing import TYPE_CHECKING, Any, Generator, Literal, Optional
from urllib.parse import urlparse

import requests
from snakemake_interface_common.exceptions import WorkflowError
from snakemake_interface_common.logging import get_logger
from snakemake_interface_storage_plugins.io import IOCacheStorageInterface, Mtime
from snakemake_interface_storage_plugins.storage_object import (
    StorageObjectRead,
    StorageObjectWrite,
)

if TYPE_CHECKING:
    from .provider import StorageProvider

__all__ = ["StorageObject"]

HTTPVerb = Literal["GET", "POST", "HEAD"]
logger = get_logger()


class StorageObject(StorageObjectRead, StorageObjectWrite):
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
        provider: StorageProvider

    async def inventory(self, cache: IOCacheStorageInterface):
        """From this file, try to find as much existence and modification date
        information as possible. Only retrieve that information that comes for free
        given the current object.
        """
        with self.httpr(self.GET_FILE_URL) as r:
            name = str(self.local_path())
            file_info = FileInfo(r)
            cache.exists_in_storage[name] = file_info.exists()
            cache.mtime[name] = Mtime(storage=file_info.last_modified())
            cache.size[name] = file_info.size()

    def get_inventory_parent(self) -> Optional[str]:
        return None

    def cleanup(self):
        pass

    def exists(self) -> bool:
        with self.httpr(self.GET_FILE_URL) as r:
            return FileInfo(r).exists()

    def mtime(self) -> float:
        with self.httpr(self.GET_FILE_URL) as r:
            return FileInfo(r).last_modified()

    def size(self) -> int:
        with self.httpr(self.GET_FILE_URL) as r:
            return FileInfo(r).size()

    def retrieve_object(self):
        self.local_path().parent.mkdir(parents=True, exist_ok=True)
        with (
            self.httpr(self.DOWNLOAD_FILE_URL, stream=True) as r,
            self.local_path().open("wb") as fh,
        ):
            for chunk in r.iter_content():
                fh.write(chunk)

    @property
    def _full_query(self) -> str:
        if (site_url := self.provider.settings.site_url) is None:
            raise WorkflowError("No site URL specified")
        if (library := self.provider.settings.library) is None:
            raise WorkflowError("No library specified")
        return "/".join([site_url, library, self.query])

    # The type: ignore is necessary because the return type is not compatible with the
    # base class:
    # https://github.com/snakemake/snakemake-interface-storage-plugins/pull/48
    def local_suffix(self) -> str:  # type: ignore
        parsed = urlparse(self._full_query)
        return f"{parsed.netloc}/{parsed.path}"

    def store_object(self):
        with self.httpr(self.DIGEST_URL, "POST") as r:
            try:
                r.raise_for_status()
            except requests.HTTPError as e:
                raise WorkflowError(
                    f"Failed to get form digest value for {self.query}"
                ) from e

            digest_value = r.json()["d"]["GetContextWebInformation"]["FormDigestValue"]

        headers = {"x-requestdigest": digest_value}

        with open(self.local_path(), "rb") as file:
            with self.httpr(
                self.UPLOAD_FILE_URL, "POST", headers=headers, data=file.read()
            ) as r:
                try:
                    r.raise_for_status()
                except requests.HTTPError as e:
                    raise WorkflowError(f"Failed to store {self.query}") from e

    def remove(self):
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
        _headers = {
            "Content-Type": "application/json; odata=verbose",
            "Accept": "application/json; odata=verbose",
        }
        _url = url.format(
            site_url=self.provider.settings.site_url,
            folder=self.provider.settings.library,
            filename=self.query,
            overwrite=str(self.provider.settings.allow_overwrite).lower(),
        )
        logger.debug(f"Requesting {verb!r} to {_url}")
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
