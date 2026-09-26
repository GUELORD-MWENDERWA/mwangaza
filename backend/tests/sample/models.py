from django.db import models

from apps.core.models import TenantModel


class Note(TenantModel):
    text = models.CharField(max_length=100)

    def __str__(self) -> str:
        return self.text


class Comment(TenantModel):
    note = models.ForeignKey(Note, on_delete=models.CASCADE, related_name="comments")
    text = models.CharField(max_length=100)

    def __str__(self) -> str:
        return self.text
