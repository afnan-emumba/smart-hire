from __future__ import annotations

from datetime import timedelta

from temporalio import workflow
from temporalio.common import RetryPolicy

from app.temporal.constants import (
    ACTIVITY_DELIVER_NOTIFICATION,
    ACTIVITY_RECORD_NOTIFICATION,
)
from app.temporal.dto import DeliverNotificationInput, NotificationDeliveryInput
from contracts.temporal import NOTIFICATION_DELIVERY_WORKFLOW_NAME
from temporal.constants import WORKFLOW_STATUS_SUCCESS
from temporal.schemas import (
    NotificationDeliveryWorkflowResult,
    NotificationRecordActivityResult,
)

# Recording the notification is a local write that either works or is genuinely
# broken, so it stays bounded. Delivery is the fallible external step and keeps
# retrying for as long as the workflow is allowed to live.
_RECORD_RETRY_POLICY = RetryPolicy(
    initial_interval=timedelta(seconds=1),
    backoff_coefficient=2.0,
    maximum_interval=timedelta(seconds=10),
    maximum_attempts=5,
)
_DELIVERY_RETRY_POLICY = RetryPolicy(
    initial_interval=timedelta(seconds=1),
    backoff_coefficient=2.0,
    maximum_interval=timedelta(minutes=5),
    maximum_attempts=0,
)


@workflow.defn(name=NOTIFICATION_DELIVERY_WORKFLOW_NAME)
class NotificationDeliveryWorkflow:
    @workflow.run
    async def run(self, input: NotificationDeliveryInput) -> dict[str, str]:
        recorded = await workflow.execute_activity(
            ACTIVITY_RECORD_NOTIFICATION,
            input,
            start_to_close_timeout=timedelta(minutes=1),
            retry_policy=_RECORD_RETRY_POLICY,
        )
        notification = NotificationRecordActivityResult.model_validate(recorded)

        delivered = await workflow.execute_activity(
            ACTIVITY_DELIVER_NOTIFICATION,
            DeliverNotificationInput(notification_id=str(notification.notification_id)),
            start_to_close_timeout=timedelta(minutes=1),
            retry_policy=_DELIVERY_RETRY_POLICY,
        )
        delivery_result = NotificationRecordActivityResult.model_validate(delivered)

        return NotificationDeliveryWorkflowResult(
            status=WORKFLOW_STATUS_SUCCESS,
            notification_id=delivery_result.notification_id,
            notification_status=delivery_result.status,
        ).model_dump(mode="json")
