from enum import Enum
from typing import Set, Dict

class WorkflowState(str, Enum):
    DRAFT = "DRAFT"
    COMPILED = "COMPILED"
    PENDING_APPROVAL = "PENDING_APPROVAL"
    RUNNING = "RUNNING"
    PAUSED = "PAUSED"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"

class TaskState(str, Enum):
    PENDING = "PENDING"
    READY = "READY"
    WAITING_APPROVAL = "WAITING_APPROVAL"
    IN_PROGRESS = "IN_PROGRESS"
    DISPATCHED_UNKNOWN = "DISPATCHED_UNKNOWN"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    SKIPPED = "SKIPPED"
    COMPENSATED = "COMPENSATED"

# Valid state transitions for workflow state machine
WORKFLOW_TRANSITIONS: Dict[WorkflowState, Set[WorkflowState]] = {
    WorkflowState.DRAFT: {WorkflowState.COMPILED, WorkflowState.CANCELLED},
    WorkflowState.COMPILED: {WorkflowState.PENDING_APPROVAL, WorkflowState.RUNNING, WorkflowState.CANCELLED},
    WorkflowState.PENDING_APPROVAL: {WorkflowState.RUNNING, WorkflowState.CANCELLED},
    WorkflowState.RUNNING: {WorkflowState.PAUSED, WorkflowState.COMPLETED, WorkflowState.FAILED, WorkflowState.CANCELLED},
    WorkflowState.PAUSED: {WorkflowState.RUNNING, WorkflowState.CANCELLED},
    WorkflowState.COMPLETED: set(),
    WorkflowState.FAILED: {WorkflowState.RUNNING}, # Retry allowed
    WorkflowState.CANCELLED: set()
}

# Valid state transitions for task state machine
TASK_TRANSITIONS: Dict[TaskState, Set[TaskState]] = {
    TaskState.PENDING: {TaskState.READY, TaskState.SKIPPED},
    TaskState.READY: {TaskState.IN_PROGRESS, TaskState.WAITING_APPROVAL, TaskState.SKIPPED, TaskState.FAILED},
    TaskState.WAITING_APPROVAL: {TaskState.IN_PROGRESS, TaskState.FAILED, TaskState.SKIPPED},
    TaskState.IN_PROGRESS: {TaskState.COMPLETED, TaskState.FAILED, TaskState.DISPATCHED_UNKNOWN},
    TaskState.DISPATCHED_UNKNOWN: {TaskState.COMPLETED, TaskState.FAILED},
    TaskState.COMPLETED: {TaskState.COMPENSATED},
    TaskState.FAILED: {TaskState.READY, TaskState.SKIPPED}, # Retry allowed
    TaskState.SKIPPED: set(),
    TaskState.COMPENSATED: set()
}

def validate_workflow_transition(current: WorkflowState, next_state: WorkflowState) -> bool:
    return next_state in WORKFLOW_TRANSITIONS.get(current, set())

def validate_task_transition(current: TaskState, next_state: TaskState) -> bool:
    return next_state in TASK_TRANSITIONS.get(current, set())
