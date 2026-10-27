"""Minimal Django storage backend that keeps uploaded files on Cloudinary (free tier).

Enabled automatically when the CLOUDINARY_URL environment variable is set
(format: cloudinary://<api_key>:<api_secret>@<cloud_name>). Files are stored
under their upload_to path; Django saves the returned public name in the DB and
url() rebuilds the public link from it.
"""
import os

import cloudinary
import cloudinary.uploader
import cloudinary.utils
from django.core.files.storage import Storage
from django.utils.deconstruct import deconstructible


@deconstructible
class CloudinaryMediaStorage(Storage):
    def _save(self, name, content):
        content.seek(0)
        # resource_type="auto" lets Cloudinary accept images, PDFs and other documents.
        result = cloudinary.uploader.upload(
            content,
            public_id=name,
            resource_type="auto",
            use_filename=True,
            unique_filename=True,
            overwrite=False,
        )
        # Store "<resource_type>/<public_id>.<ext>" so url() can rebuild the link later.
        ext = result.get("format")
        public = result["public_id"] + (f".{ext}" if ext and result["resource_type"] != "raw" else "")
        return f"{result['resource_type']}/{public}"

    def exists(self, name):
        # Names are made unique by Cloudinary, so Django never needs to rename.
        return False

    def url(self, name):
        resource_type, _, public = name.partition("/")
        url, _ = cloudinary.utils.cloudinary_url(public, resource_type=resource_type, secure=True)
        return url

    def delete(self, name):
        resource_type, _, public = name.partition("/")
        if resource_type != "raw":
            public = os.path.splitext(public)[0]
        cloudinary.uploader.destroy(public, resource_type=resource_type)

    def size(self, name):
        return 0

    def _open(self, name, mode="rb"):
        raise NotImplementedError("Files are served directly from Cloudinary; use .url instead.")
