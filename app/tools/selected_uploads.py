"""Normalize selected upload IDs for tools, agents and terminal commands."""

from uuid import UUID


def selected_uploads(value: UUID | list[UUID]) -> list[UUID]:
    values = [value] if isinstance(value, UUID) else value
    if not values:
        raise ValueError("Select at least one upload")
    return list(dict.fromkeys(UUID(str(item)) for item in values))
