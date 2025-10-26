from pydantic import BaseModel, field_validator
from datetime import datetime
from typing import Optional


class LLMResponse(BaseModel):
    date: str  # YYYY-MM-DD
    time: str  # HH:MM:SS или ???
    end_time: Optional[str] = None  # HH:MM:SS (опционально)
    description: str
    priority: int = 2  # 1-высокий, 2-средний, 3-низкий
    original_text: Optional[str] = None

    @field_validator("date")
    def validate_date(cls, v):
        try:
            datetime.strptime(v, "%Y-%m-%d")
            return v
        except ValueError:
            raise ValueError("Неверный формат даты. Используйте YYYY-MM-DD")

    @field_validator("time")
    def validate_time(cls, v):
        if v == "???":
            return v
        try:
            datetime.strptime(v, "%H:%M:%S")
            return v
        except ValueError:
            raise ValueError("Неверный формат времени. Используйте HH:MM:SS")

    @field_validator("end_time")
    def validate_end_time(cls, v):
        if v is None:
            return v
        try:
            datetime.strptime(v, "%H:%M:%S")
            return v
        except ValueError:
            raise ValueError("Неверный формат времени окончания. Используйте HH:MM:SS")

    @field_validator("priority")
    def validate_priority(cls, v):
        if v not in [1, 2, 3]:
            return 2
        return v


class EventConflict(BaseModel):
    is_conflict: bool
    conflicting_event_description: Optional[str] = None
    conflicting_event_time: Optional[str] = None
