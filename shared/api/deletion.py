from __future__ import annotations

import uuid

from pydantic import BaseModel

from contracts.enums import DeletionState


class DeletionAcceptedResponse(BaseModel):
    """202 body returned by endpoints that hand a delete cascade to Temporal.

    Poll the deleted resource to follow progress: it keeps returning
    ``deletion_state: deleting`` until the workflow's final activity removes it,
    after which the read returns 404.
    """

    resource_id: uuid.UUID
    workflow_id: str
    deletion_state: DeletionState = DeletionState.DELETING
