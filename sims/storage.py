"""Minimal Django storage backend that keeps uploaded files on Cloudinary (free tier).

Enabled automatically when the CLOUDINARY_URL environment variable is set
(format: cloudinary://<api_key>:<api_secret>@<cloud_name>). Files are stored
under their upload_to path; Django saves the returned public name in the DB and
url() rebuilds the public link from it.
"""
import os

from django.conf import settings
from django.core.files.storage import FileSystemStorage, Storage
from django.utils.deconstruct import deconstructible
from django.utils.functional import cached_property


@deconstructible
class CloudinaryMediaStorage(Storage):
    def _save(self, name, content):
        import cloudinary.uploader

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
        import cloudinary.utils

        resource_type, _, public = name.partition("/")
        url, _ = cloudinary.utils.cloudinary_url(public, resource_type=resource_type, secure=True)
        return url

    def delete(self, name):
        import cloudinary.uploader

        resource_type, _, public = name.partition("/")
        if resource_type != "raw":
            public = os.path.splitext(public)[0]
        cloudinary.uploader.destroy(public, resource_type=resource_type)

    def size(self, name):
        return 0

    def _open(self, name, mode="rb"):
        raise NotImplementedError("Files are served directly from Cloudinary; use .url instead.")



@deconstructible
class PrivateLocalStorage(FileSystemStorage):
    """Local disk storage outside MEDIA_ROOT, with no public URL (used for Aadhaar copies)."""

    @cached_property
    def base_location(self):
        return self._value_or_setting(self._location, settings.PRIVATE_MEDIA_ROOT)

    def _clear_cached_properties(self, setting, **kwargs):
        super()._clear_cached_properties(setting, **kwargs)
        if setting == "PRIVATE_MEDIA_ROOT":
            self.__dict__.pop("base_location", None)
            self.__dict__.pop("location", None)

    def url(self, name):
        raise ValueError("Private files have no public URL; serve them through the protected view.")


@deconstructible
class PrivateCloudinaryStorage(CloudinaryMediaStorage):
    """Cloudinary storage using type="authenticated": files cannot be fetched without a signed link.

    url() returns a short-lived signed link, to be handed out only by the
    password-protected Aadhaar copy view.
    """

    def _save(self, name, content):
        import cloudinary.uploader

        content.seek(0)
        result = cloudinary.uploader.upload(
            content,
            public_id=name,
            resource_type="auto",
            type="authenticated",
            use_filename=True,
            unique_filename=True,
            overwrite=False,
        )
        ext = result.get("format")
        public = result["public_id"] + (f".{ext}" if ext and result["resource_type"] != "raw" else "")
        return f"{result['resource_type']}/{public}"

    def url(self, name):
        import time

        import cloudinary.utils

        resource_type, _, public = name.partition("/")
        url, _ = cloudinary.utils.cloudinary_url(
            public,
            resource_type=resource_type,
            type="authenticated",
            sign_url=True,
            secure=True,
            expires_at=int(time.time()) + 120,
        )
        return url

    def delete(self, name):
        import cloudinary.uploader

        resource_type, _, public = name.partition("/")
        if resource_type != "raw":
            public = os.path.splitext(public)[0]
        cloudinary.uploader.destroy(public, resource_type=resource_type, type="authenticated")
