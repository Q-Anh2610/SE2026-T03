"""Import đầy đủ models để Alembic nhận diện metadata."""

from app.models.asset import Asset
from app.models.feedback import Feedback
from app.models.search_event import SearchEvent
from app.models.job import Job

__all__ = ["Asset", "Feedback", "SearchEvent", "Job"]
