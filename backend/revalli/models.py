"""Importa todos os modelos para que o Alembic e o metadata os enxerguem."""

from revalli.modules.ai.models import (
    AIProvider,
    AISuggestion,
    AIUsage,
    InstanceSetting,
    RecordEmbedding,
)
from revalli.modules.auth.models import Invitation, Session, User
from revalli.modules.corpus.models import Chunk, ChunkEmbedding, CorpusMessage
from revalli.modules.extraction.models import Extraction, ExtractionForm, FormVersion
from revalli.modules.fulltext.models import FilePage, RecordFile, Study, StudyReport
from revalli.modules.meta.models import GradeRow, MetaAnalysis
from revalli.modules.projects.models import Project, ProjectMember
from revalli.modules.records.models import (
    DuplicateGroup,
    Job,
    NotDuplicate,
    Record,
    Search,
)
from revalli.modules.screening.models import DecisionEvent, ExclusionReason
from revalli.modules.synthesis.models import ChecklistEntry, Code, Excerpt, ExcerptCode
from revalli.modules.tokens.models import ApiToken
from revalli.modules.watches.models import Watch

__all__ = [
    "Watch",
    "ApiToken",
    "Chunk",
    "ChunkEmbedding",
    "CorpusMessage",
    "GradeRow",
    "MetaAnalysis",
    "ChecklistEntry",
    "Code",
    "Excerpt",
    "ExcerptCode",
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
