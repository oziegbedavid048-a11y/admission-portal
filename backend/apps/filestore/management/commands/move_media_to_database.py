"""Copy files saved on disk before uploads moved into the database.

    python manage.py move_media_to_database

Walks MEDIA_ROOT and stores every file whose record still points at it. Files
already in the database are left alone, so it is safe to run more than once.
Nothing on disk is deleted.
"""

import mimetypes
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand

from apps.filestore.models import StoredFile


class Command(BaseCommand):
    help = "Copy uploaded files from MEDIA_ROOT into the database."

    def handle(self, *args, **options):
        root = Path(settings.MEDIA_ROOT)
        if not root.exists():
            self.stdout.write("No media folder here, so there is nothing to move.")
            return
        moved = skipped = 0
        for path in root.rglob("*"):
            if not path.is_file():
                continue
            name = path.relative_to(root).as_posix()
            if StoredFile.objects.filter(name=name).exists():
                skipped += 1
                continue
            data = path.read_bytes()
            StoredFile.objects.create(
                name=name,
                content=data,
                size=len(data),
                content_type=mimetypes.guess_type(name)[0] or "application/octet-stream",
            )
            moved += 1
        self.stdout.write(self.style.SUCCESS(f"Moved {moved} file(s); {skipped} were already stored."))
