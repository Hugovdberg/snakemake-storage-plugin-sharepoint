"""Module to define the storage provider settings."""

import dataclasses
import importlib
import re
from typing import List, Optional

import requests
import requests.auth
from snakemake_interface_common.exceptions import WorkflowError
from snakemake_interface_storage_plugins.settings import StorageProviderSettingsBase

__all__ = ["StorageProviderSettings"]

AUTH_METAVAR = "[PACKAGE.]AUTH_TYPE[=ARG1,ARG2,...]"
AUTH_REGEX = re.compile(
    r"^((?P<package>[\w\.]+)\.)?(?P<type>\w+)(=(?P<arg>(\w+,?)+))?$"
)


class _PredefinedHTTPAuth:
    HTTPBasicAuth = requests.auth.HTTPBasicAuth
    HTTPDigestAuth = requests.auth.HTTPDigestAuth
    HTTPProxyAuth = requests.auth.HTTPProxyAuth


def _split(s: Optional[str], sep: str) -> List[str]:
    if s is None:
        return []
    return s.split(sep)


def parse_auth(arg: Optional[str]) -> Optional[requests.auth.AuthBase]:
    """Parse the authentication options from the command line."""
    if arg is None:
        return None

    matches = AUTH_REGEX.match(arg)
    if not matches:
        raise WorkflowError(
            f"Authentication requires a string of the form {AUTH_METAVAR}"
        )
    auth_package = matches.group("package")
    auth_type = matches.group("type")
    auth_args = _split(matches.group("arg"), ",")

    if auth_package:
        try:
            auth_module = importlib.import_module(auth_package)
        except ModuleNotFoundError:
            raise WorkflowError(
                f"Authentication package {auth_package} not found. "
                "Please make sure it is installed."
            ) from None
    else:
        auth_module = _PredefinedHTTPAuth

    try:
        auth_class: type[requests.auth.AuthBase] = getattr(auth_module, auth_type)
    except AttributeError as e:
        raise WorkflowError(
            f"Authentication type {auth_type} not supported. "
            "Please choose one of HTTPBasicAuth, HTTPDigestAuth, or HTTPProxyAuth, "
            "or specify the full path like module.AuthClass"
            " (e.g. requests.auth.HTTPBasicAuth)."
        ) from e

    try:
        return auth_class(*auth_args)
    except TypeError as e:
        raise WorkflowError("Failed to initialize the authentication method.") from e


def unparse_auth(auth: requests.auth.AuthBase) -> str:
    """Write the used authentication method to a string."""
    return f"{auth.__class__.__module__}.{auth.__class__.__name__}"


# Define settings for your storage plugin (e.g. host url, credentials).
# They will occur in the Snakemake CLI as --storage-<storage-plugin-name>-<param-name>
# Make sure that all defined fields are 'Optional' and specify a default value
# of None or anything else that makes sense in your case.
# Note that we allow storage plugin settings to be tagged by the user. That means,
# that each of them can be specified multiple times (an implicit nargs=+), and
# the user can add a tag in front of each value (e.g. tagname1:value1 tagname2:value2).
# This way, a storage plugin can be used multiple times within a workflow with different
# settings.
@dataclasses.dataclass
class StorageProviderSettings(StorageProviderSettingsBase):
    """Defines the custom settings for the SharePoint storage provider."""

    auth: Optional[requests.auth.AuthBase] = dataclasses.field(
        default=None,
        metadata={
            "help": (
                "HTTP(S) authentication. AUTH_TYPE is the class name of "
                "requests.auth (e.g. HTTPBasicAuth), ARG1,ARG2,... are the arguments "
                "required by the specified type. PACKAGE is the full path to the "
                "module from which to import the class (semantically this does "
                "'from PACKAGE import AUTH_TYPE')."
            ),
            "metavar": AUTH_METAVAR,
            "parse_func": parse_auth,
            "unparse_func": unparse_auth,
            "env_var": True,
        },
    )
    allow_redirects: Optional[bool] = dataclasses.field(
        default=True,
        metadata={
            "help": "Follow redirects when retrieving files.",
        },
    )
    site_url: Optional[str] = dataclasses.field(
        default=None,
        metadata={
            "help": "The URL of the SharePoint site.",
            "env_var": True,
        },
    )
    allow_overwrite: Optional[bool] = dataclasses.field(
        default=None,
        metadata={
            "help": "Allow overwriting files in the SharePoint site.",
        },
    )
    upload_timeout: int = dataclasses.field(
        default=1000,
        metadata={
            "help": "The timeout in milliseconds for uploading files.",
        },
    )
