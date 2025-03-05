"""Snakemake storage plugin for Microsoft SharePoint."""

__author__ = "Hugo Lapre"
__copyright__ = "Copyright 2024, Hugo Lapre"
__email__ = "github@tbdwebdesign.nl"
__license__ = "MIT"
__version__ = "0.4.4"

from .object import StorageObject
from .provider import StorageProvider
from .settings import StorageProviderSettings

__all__ = ["StorageProviderSettings", "StorageProvider", "StorageObject"]
