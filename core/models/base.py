import uuid
from django.db import models
from django.conf import settings


class BaseModel(models.Model):
    """
    Abstract base model for all models in the system.
    Provides UUID primary key and timestamp tracking.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True
        indexes = [
            models.Index(fields=['created_at']),
        ]


class CompanyScopedModel(BaseModel):
    """
    Abstract model for all company-scoped entities.
    Ensures data isolation per company (multi-tenancy).
    """
    company = models.ForeignKey(
        "company.Company",
        on_delete=models.CASCADE,
        related_name="%(app_label)s_%(class)s_set"
    )

    class Meta:
        abstract = True
        indexes = [
            models.Index(fields=['company', 'created_at']),
        ]
