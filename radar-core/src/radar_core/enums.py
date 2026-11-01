"""Enumerations shared across the radar for scoring, findings, evidence and roadmap state."""

from enum import StrEnum


class ScoringModel(StrEnum):
    """Scoring model used to compute a criterion's score: fixed scale or four-state status."""

    FIXED_SCALE = "FIXED_SCALE"
    STATUS_4STATE = "STATUS_4STATE"


class ScoreLevel(StrEnum):
    """Level at which a score applies: a single criterion, a category, or the global portfolio."""

    CRITERION = "CRITERION"
    CATEGORY = "CATEGORY"
    GLOBAL = "GLOBAL"


class Confidence(StrEnum):
    """Confidence level attached to a score or a finding: HIGH, MEDIUM or LOW."""

    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"


class FindingSeverity(StrEnum):
    """Severity of a finding, from CRITICAL down to INFO."""

    CRITICAL = "CRITICAL"
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"
    INFO = "INFO"


class FindingStatus(StrEnum):
    """Lifecycle status of a finding: open, resolved, or accepted as won't fix."""

    OPEN = "OPEN"
    RESOLVED = "RESOLVED"
    WONT_FIX = "WONT_FIX"


class HumanVerdict(StrEnum):
    """Human review verdict on a finding: unreviewed, true positive, or false positive."""

    UNREVIEWED = "UNREVIEWED"
    TRUE_POSITIVE = "TRUE_POSITIVE"
    FALSE_POSITIVE = "FALSE_POSITIVE"


class EvidenceType(StrEnum):
    """Kind of evidence backing a finding or score: tool output, human confirmation or reference."""

    TOOL_OUTPUT_EXCERPT = "TOOL_OUTPUT_EXCERPT"
    HUMAN_CONFIRMATION = "HUMAN_CONFIRMATION"
    EXTERNAL_REFERENCE = "EXTERNAL_REFERENCE"


class RoadmapStatus(StrEnum):
    """Progress state of a roadmap item: to do, in progress, done, or won't fix."""

    TODO = "TODO"
    IN_PROGRESS = "IN_PROGRESS"
    DONE = "DONE"
    WONT_FIX = "WONT_FIX"
