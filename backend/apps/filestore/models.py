"""Uploaded files, kept in the database.

The web host's own disk is wiped on every deploy and restart, so a file saved
there is gone within days while the record pointing at it lives on. Keeping the
bytes in the database puts each file next to its record, with the same backups,
and nothing an applicant uploads depends on the web server's disk.

Every file is compressed before it gets here (see
apps/applications/compression.py), which is what keeps this table small.
"""

from django.db import models


class StoredFile(models.Model):
    name = models.CharField(max_length=512, unique=True)
    content = models.BinaryField()
    size = models.PositiveIntegerField(default=0)
    content_type = models.CharField(max_length=100, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("-created_at",)
        verbose_name = "stored file"
        verbose_name_plural = "stored files"

    def __str__(self):
        return self.name
