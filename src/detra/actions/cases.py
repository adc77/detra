"""Case management for tracking issues."""

import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional
from uuid import uuid4


class CaseStatus(str, Enum):
    """Status of a case."""
    OPEN = "open"
    IN_PROGRESS = "in_progress"
    RESOLVED = "resolved"
    CLOSED = "closed"


class CasePriority(str, Enum):
    """Priority of a case."""
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


@dataclass
class CaseNote:
    """A note on a case."""
    content: str
    author: str = "vertiguard"
    timestamp: float = field(default_factory=time.time)


@dataclass
class Case:
    """
    Represents a case for tracking an issue.

    Cases are used to track issues that need investigation
    or follow-up but may not warrant a full incident.
    """
    title: str
    description: str
    priority: CasePriority
    case_id: str = field(default_factory=lambda: str(uuid4()))
    status: CaseStatus = CaseStatus.OPEN
    node_name: Optional[str] = None
    category: Optional[str] = None
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)
    resolved_at: Optional[float] = None
    notes: list[CaseNote] = field(default_factory=list)
    related_trace_ids: list[str] = field(default_factory=list)
    tags: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    def add_note(self, content: str, author: str = "vertiguard") -> None:
        """Add a note to the case."""
        self.notes.append(CaseNote(content=content, author=author))
        self.updated_at = time.time()

    def update_status(self, status: CaseStatus) -> None:
        """Update the case status."""
        self.status = status
        self.updated_at = time.time()
        if status == CaseStatus.RESOLVED:
            self.resolved_at = time.time()

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "case_id": self.case_id,
            "title": self.title,
            "description": self.description,
            "priority": self.priority.value,
            "status": self.status.value,
            "node_name": self.node_name,
            "category": self.category,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "resolved_at": self.resolved_at,
            "notes": [
                {"content": n.content, "author": n.author, "timestamp": n.timestamp}
                for n in self.notes
            ],
            "related_trace_ids": self.related_trace_ids,
            "tags": self.tags,
            "metadata": self.metadata,
        }


class CaseManager:
    """
    Manages cases for tracking issues.

    Provides CRUD operations for cases and aggregation
    utilities.
    """

    def __init__(self, max_cases: int = 1000):
        """
        Initialize the case manager.

        Args:
            max_cases: Maximum cases to keep in memory.
        """
        self.max_cases = max_cases
        self._cases: dict[str, Case] = {}

    def create_case(
        self,
        title: str,
        description: str,
        priority: CasePriority,
        node_name: Optional[str] = None,
        category: Optional[str] = None,
        tags: Optional[list[str]] = None,
        metadata: Optional[dict[str, Any]] = None,
    ) -> Case:
        """
        Create a new case.

        Args:
            title: Case title.
            description: Case description.
            priority: Case priority.
            node_name: Related node name.
            category: Issue category.
            tags: Case tags.
            metadata: Additional metadata.

        Returns:
            Created Case instance.
        """
        case = Case(
            title=title,
            description=description,
            priority=priority,
            node_name=node_name,
            category=category,
            tags=tags or [],
            metadata=metadata or {},
        )

        self._cases[case.case_id] = case
        self._trim_cases()

        return case

    def get_case(self, case_id: str) -> Optional[Case]:
        """Get a case by ID."""
        return self._cases.get(case_id)

    def update_case(
        self,
        case_id: str,
        status: Optional[CaseStatus] = None,
        priority: Optional[CasePriority] = None,
        note: Optional[str] = None,
    ) -> Optional[Case]:
        """
        Update a case.

        Args:
            case_id: Case ID.
            status: New status.
            priority: New priority.
            note: Note to add.

        Returns:
            Updated case or None if not found.
        """
        case = self._cases.get(case_id)
        if not case:
            return None

        if status:
            case.update_status(status)

        if priority:
            case.priority = priority
            case.updated_at = time.time()

        if note:
            case.add_note(note)

        return case

    def close_case(self, case_id: str, resolution_note: Optional[str] = None) -> Optional[Case]:
        """
        Close a case.

        Args:
            case_id: Case ID.
            resolution_note: Optional resolution note.

        Returns:
            Closed case or None if not found.
        """
        case = self._cases.get(case_id)
        if not case:
            return None

        if resolution_note:
            case.add_note(f"Resolution: {resolution_note}")

        case.update_status(CaseStatus.CLOSED)
        return case

    def list_cases(
        self,
        status: Optional[CaseStatus] = None,
        priority: Optional[CasePriority] = None,
        node_name: Optional[str] = None,
        limit: int = 50,
    ) -> list[Case]:
        """
        List cases with optional filtering.

        Args:
            status: Filter by status.
            priority: Filter by priority.
            node_name: Filter by node name.
            limit: Maximum cases to return.

        Returns:
            List of matching cases.
        """
        cases = list(self._cases.values())

        if status:
            cases = [c for c in cases if c.status == status]

        if priority:
            cases = [c for c in cases if c.priority == priority]

        if node_name:
            cases = [c for c in cases if c.node_name == node_name]

        # Sort by created_at descending
        cases.sort(key=lambda c: c.created_at, reverse=True)

        return cases[:limit]

    def get_open_cases(self) -> list[Case]:
        """Get all open cases."""
        return self.list_cases(status=CaseStatus.OPEN)

    def get_critical_cases(self) -> list[Case]:
        """Get all critical priority cases."""
        return self.list_cases(priority=CasePriority.CRITICAL)

    def get_summary(self) -> dict[str, Any]:
        """Get a summary of cases."""
        status_counts = {s.value: 0 for s in CaseStatus}
        priority_counts = {p.value: 0 for p in CasePriority}

        for case in self._cases.values():
            status_counts[case.status.value] += 1
            priority_counts[case.priority.value] += 1

        return {
            "total": len(self._cases),
            "by_status": status_counts,
            "by_priority": priority_counts,
        }

    def _trim_cases(self) -> None:
        """Trim cases to stay under max limit."""
        if len(self._cases) <= self.max_cases:
            return

        # Sort by updated_at, keep most recent
        sorted_cases = sorted(
            self._cases.values(),
            key=lambda c: c.updated_at,
            reverse=True,
        )

        # Keep only the most recent cases
        self._cases = {c.case_id: c for c in sorted_cases[: self.max_cases]}

    def create_from_flag(
        self,
        node_name: str,
        score: float,
        category: str,
        reason: str,
        trace_id: Optional[str] = None,
    ) -> Case:
        """
        Create a case from a flag event.

        Args:
            node_name: Node name.
            score: Adherence score.
            category: Flag category.
            reason: Flag reason.
            trace_id: Related trace ID.

        Returns:
            Created case.
        """
        priority = (
            CasePriority.CRITICAL if score < 0.3
            else CasePriority.HIGH if score < 0.5
            else CasePriority.MEDIUM if score < 0.7
            else CasePriority.LOW
        )

        case = self.create_case(
            title=f"Flag: {node_name} - {category}",
            description=reason,
            priority=priority,
            node_name=node_name,
            category=category,
            tags=[f"score:{score:.2f}", f"category:{category}"],
            metadata={"score": score},
        )

        if trace_id:
            case.related_trace_ids.append(trace_id)

        return case
