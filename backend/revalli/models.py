"""Importa todos os modelos para que o Alembic e o metadata os enxerguem."""

from revalli.modules.auth.models import Invitation, Session, User
from revalli.modules.projects.models import Project, ProjectMember
from revalli.modules.records.models import (
    DuplicateGroup,
    Job,
    NotDuplicate,
    Record,
    Search,
)

__all__ = [
    "DuplicateGroup",
    "Invitation",
    "Job",
    "NotDuplicate",
    "Project",
    "ProjectMember",
    "Record",
    "Search",
    "Session",
    "User",
]
