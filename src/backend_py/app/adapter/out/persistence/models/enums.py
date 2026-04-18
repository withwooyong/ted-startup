from __future__ import annotations

from enum import Enum


class MarketType(str, Enum):
    KOSPI = "KOSPI"
    KOSDAQ = "KOSDAQ"


class SignalType(str, Enum):
    RAPID_DECLINE = "RAPID_DECLINE"
    TREND_REVERSAL = "TREND_REVERSAL"
    SHORT_SQUEEZE = "SHORT_SQUEEZE"


class SignalGrade(str, Enum):
    A = "A"
    B = "B"
    C = "C"
    D = "D"

    @classmethod
    def from_score(cls, score: int) -> SignalGrade:
        if score >= 80:
            return cls.A
        if score >= 60:
            return cls.B
        if score >= 40:
            return cls.C
        return cls.D


class BatchJobStatus(str, Enum):
    SUCCESS = "SUCCESS"
    FAILED = "FAILED"
    RUNNING = "RUNNING"
