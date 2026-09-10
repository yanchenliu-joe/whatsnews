"""Why-it-matters generation (rule-based + batch AI refinement)."""

from app.wim.generator import generate_why_it_matters
from app.wim.service import fill_missing_why_it_matters

__all__ = [
    "generate_why_it_matters",
    "fill_missing_why_it_matters",
]
