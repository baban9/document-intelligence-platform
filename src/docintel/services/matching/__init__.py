"""Resume-to-job matching service."""

from docintel.services.matching.models import MatchResult
from docintel.services.matching.scorer import match_resume_to_job

__all__ = ["MatchResult", "match_resume_to_job"]
