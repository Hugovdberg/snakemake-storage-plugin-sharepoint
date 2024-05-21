A Snakemake storage plugin for reading and writing files on Microsoft Sharepoint sites.
For now only tested with Sharepoint 2016 on premise, so if any issues arise with your
SharePoint site, please file an issue on the [GitHub repository](https://github.com/Hugovdberg/snakemake-storage-plugin-sharepoint).

## Overwriting files

Overwriting existing files is disabled by default.
It can be enabled either for the storage provider or individual files.
For individual files you add `?overwrite=...` to your query
(or simply add `?overwrite` to set it to `true`).
For the storage provider you set `allow_overwrite` in the settings
In both cases the setting can be either True, False or None.
The table below shows how the two settings interact to set the overwrite behaviour for
an individual file:

|                  | allow_overwrite=False | allow_overwrite=None | allow_overwrite=True |
|-----------------:|:---------------------:|:--------------------:|:--------------------:|
| ?overwrite=false |         False         |         False        |         False        |
|  ?overwrite=none |         False         |         False        |         True         |
|  ?overwrite=true |         False         |         True         |         True         |
