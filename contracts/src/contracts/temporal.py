from __future__ import annotations

"""Workflow names and task queues that one service starts on another service's worker.

Service-local workflow, activity, and task-queue names stay in each service's own
``app/temporal/constants.py``. Only the identifiers that cross a service boundary
belong here, so the dependency is declared in the shared contract package rather
than re-typed as string literals in the calling service.
"""

JOB_DELETION_WORKFLOW_NAME = "job-deletion-workflow"
JOB_DELETION_TASK_QUEUE = "job-deletion"

NOTIFICATION_DELIVERY_WORKFLOW_NAME = "notification-delivery-workflow"
NOTIFICATION_DELIVERY_TASK_QUEUE = "notification-delivery"
