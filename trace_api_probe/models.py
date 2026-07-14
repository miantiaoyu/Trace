from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class StatusSnapshot(StrictModel):
    time: str | None = None
    status: str | None = None
    location: str | None = None
    mode: str | None = None


class VesselSummary(StrictModel):
    name: str | None = None
    voyage: str | None = None
    imo: str | None = None


class TrackingEvent(StatusSnapshot):
    vessel: str | None = None
    voyage: str | None = None
    imo: str | None = None
    time_type: Literal["ACTUAL", "EXPECTED"] | None = None


class Coverage(StrictModel):
    current: bool = False
    next_expected: bool = False
    events: bool = False
    vessel: bool = False
    eta: bool = False


class TrackingSummary(StrictModel):
    schema_version: Literal["1.1"] = "1.1"
    carrier: str = Field(min_length=1)
    container: str = Field(min_length=1)
    current: StatusSnapshot = Field(default_factory=StatusSnapshot)
    next_expected: StatusSnapshot = Field(default_factory=StatusSnapshot)
    vessel: VesselSummary = Field(default_factory=VesselSummary)
    origin: str | None = None
    destination: str | None = None
    destination_eta: str | None = None
    events: list[TrackingEvent] = Field(default_factory=list)
    coverage: Coverage = Field(default_factory=Coverage)


def validate_tracking_summary(value: object) -> dict[str, object]:
    return TrackingSummary.model_validate(value).model_dump(mode="json")


def new_tracking_summary(carrier: str, container: str) -> dict[str, object]:
    return TrackingSummary(carrier=carrier, container=container).model_dump(mode="json")
