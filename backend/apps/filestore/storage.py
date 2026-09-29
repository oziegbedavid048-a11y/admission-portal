"""A Django storage backend that keeps uploaded files in the database.

Every FileField in the project uses it by default, so documents, letters,
correction evidence, support attachments and profile pictures all land in the
`filestore_storedfile` table. A file's URL is `/media/<name>`, answered by
config/media.py, which reads the bytes back from here.
"""

import mimetypes

from django.conf import settings
from django.core.files.base import ContentFile
from django.core.files.storage import Storage
from django.utils.deconstruct import deconstructible


@deconstructible
class DatabaseStorage(Storage):
    def _model(self):
        from .models import StoredFile

        return StoredFile

    def _open(self, name, mode="rb"):
        row = self._model().objects.filter(name=name).only("content", "name").first()
        if row is None:
            raise FileNotFoundError(name)
        file = ContentFile(bytes(row.content), name=name)
        return file

    def _save(self, name, content):
        content.seek(0)
        data = content.read()
        if isinstance(data, str):
            data = data.encode()
        content_type = (
            getattr(content, "content_type", None)
            or mimetypes.guess_type(name)[0]
            or "application/octet-stream"
        )
        self._model().objects.update_or_create(
            name=name,
            defaults={"content": data, "size": len(data), "content_type": content_type},
        )
        return name

    def delete(self, name):
        self._model().objects.filter(name=name).delete()

    def exists(self, name):
        return self._model().objects.filter(name=name).exists()

    def size(self, name):
        row = self._model().objects.filter(name=name).only("size").first()
        if row is None:
            raise FileNotFoundError(name)
        return row.size

    def url(self, name):
        return f"{settings.MEDIA_URL}{name}"

    def listdir(self, path):
        prefix = path.rstrip("/") + "/" if path else ""
        names = self._model().objects.filter(name__startswith=prefix).values_list("name", flat=True)
        dirs, files = set(), []
        for full in names:
            rest = full[len(prefix):]
            if "/" in rest:
                dirs.add(rest.split("/", 1)[0])
            else:
                files.append(rest)
        return sorted(dirs), files

    def get_created_time(self, name):
        row = self._model().objects.filter(name=name).only("created_at").first()
        if row is None:
            raise FileNotFoundError(name)
        return row.created_at

    get_modified_time = get_created_time
