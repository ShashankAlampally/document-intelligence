"""Configurable hybrid defaults plus optional per-search overrides."""

from typing import Literal

from pydantic import BaseModel, Field


class HybridOptions(BaseModel):
    mode: Literal["vector", "hybrid"] = "hybrid"
    vector_candidates: int = Field(default=20, ge=1, le=100)
    keyword_candidates: int = Field(default=20, ge=1, le=100)
    vector_weight: float = Field(default=1, gt=0, allow_inf_nan=False)
    keyword_weight: float = Field(default=1, gt=0, allow_inf_nan=False)
    rerank: bool = False
    rerank_candidates: int = Field(default=20, ge=1, le=100)
    rrf_k: int = Field(default=60, ge=1)


class SearchTuning(BaseModel):
    mode: Literal["vector", "hybrid"] | None = None
    vector_candidates: int | None = Field(default=None, ge=1, le=100)
    keyword_candidates: int | None = Field(default=None, ge=1, le=100)
    vector_weight: float | None = Field(default=None, gt=0, allow_inf_nan=False)
    keyword_weight: float | None = Field(default=None, gt=0, allow_inf_nan=False)
    rerank: bool | None = None
    rerank_candidates: int | None = Field(default=None, ge=1, le=100)
    rrf_k: int | None = Field(default=None, ge=1)
    field_name: str | None = Field(default=None, min_length=1, max_length=100)

    def resolve(self, settings) -> HybridOptions:
        values = {name: getattr(settings, f"search_{name}") for name in HybridOptions.model_fields}
        boost = settings.search_field_keyword_boosts.get(self.field_name, 1)
        values["keyword_weight"] *= boost
        for name in HybridOptions.model_fields:
            if getattr(self, name) is not None:
                values[name] = getattr(self, name)
        return HybridOptions(**values)
