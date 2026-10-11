"""Importa todos os modelos para que o Alembic e o metadata os enxerguem."""

from revalli.modules.ai.models import (
    AIProvider,
    AISuggestion,
    AIUsage,
    InstanceSetting,
    RecordEmbedding,
)
from revalli.modules.auth.models import Invitation, Session, User
from revalli.modules.extraction.models import Extraction, ExtractionForm, FormVersion
from revalli.modules.fulltext.models import FilePage, RecordFile, Study, StudyReport
from revalli.modules.projects.models import Project, ProjectMember
from revalli.modules.records.models import (
    DuplicateGroup,
    Job,
    NotDuplicate,
    Record,
    Search,
)
from revalli.modules.screening.models import DecisionEvent, ExclusionReason

__all__ = [
    "AIProvider",
    "AISuggestion",
    "AIUsage",
    "InstanceSetting",
    "RecordEmbedding",
    "DecisionEvent",
    "DuplicateGroup",
    "Extraction",
    "ExtractionForm",
    "FormVersion",
    "FilePage",
    "ExclusionReason",
    "Invitation",
    "Job",
    "NotDuplicate",
    "Project",
    "ProjectMember",
    "Record",
    "RecordFile",
    "Search",
    "Session",
    "Study",
    "StudyReport",
    "User",
]
