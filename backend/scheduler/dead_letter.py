import time
from typing import Dict, List, Optional
from pydantic import BaseModel, Field

class DeadLetterEntry(BaseModel):
    entry_id: str
    job_id: str
    stage_id: str
    task_reference: str
    failure_class: str
    attempt_history: List[dict]
    traceback_artifact_ref: Optional[str] = None
    worker_history: List[str]
    resource_history: List[dict]
    last_checkpoint_id: Optional[str] = None
    artifact_lineage: List[str]
    recovery_guidance: str
    created_at: float = Field(default_factory=time.time)
    replayed: bool = False
    replayed_at: Optional[float] = None
    audit_event_id: Optional[str] = None

class DeadLetterManager:
    def __init__(self):
        self.entries: Dict[str, DeadLetterEntry] = {}

    def add_entry(self, entry: DeadLetterEntry) -> DeadLetterEntry:
        self.entries[entry.entry_id] = entry
        return entry

    def get_entry(self, entry_id: str) -> Optional[DeadLetterEntry]:
        return self.entries.get(entry_id)

    def approve_replay(self, entry_id: str, operator_id: str) -> bool:
        entry = self.entries.get(entry_id)
        if entry and not entry.replayed:
            entry.replayed = True
            entry.replayed_at = time.time()
            entry.audit_event_id = f"audit_replay_{operator_id}_{entry_id}_{time.time()}"
            return True
        return False

    def list_pending(self) -> List[DeadLetterEntry]:
        return [entry for entry in self.entries.values() if not entry.replayed]

    def count_by_failure_class(self) -> Dict[str, int]:
        counts = {}
        for entry in self.entries.values():
            counts[entry.failure_class] = counts.get(entry.failure_class, 0) + 1
        return counts
