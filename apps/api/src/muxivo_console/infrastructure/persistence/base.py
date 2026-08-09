"""Console persistence metadata; application and domain layers never import it."""

from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    """Base class for Console-owned database mappings."""
