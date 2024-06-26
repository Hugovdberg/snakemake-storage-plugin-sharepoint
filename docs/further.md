For now, the `site_url` setting is a required setting on the storage provider.
This is because the URL to a document cannot uniquely be parsed into the separate components
necessary for downloading and uploading on SharePoint (which are: site collection, library, 
and filename).

Also, overwriting files on SharePoint is disabled by default, and needs to be enabled on the 
storage provider using the `allow_overwrite` setting.

Finally, removing files from the remote location is not implemented at all, follow
[this issue](https://github.com/Hugovdberg/snakemake-storage-plugin-sharepoint/issues/15) 
for the current status.
Contributions to implement this in a way such that not the entire version history is 
removed are welcome.
