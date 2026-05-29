JOB_PUBLISHED_TOPIC = "smarthire.jobs.published.v1"
APPLICATION_RECEIVED_TOPIC = "smarthire.applications.received.v1"

JOB_PUBLISHED_EVENT_TYPE = "JobPublished"
APPLICATION_RECEIVED_EVENT_TYPE = "ApplicationReceived"


def schema_subject_for_topic(topic_name: str) -> str:
    return f"{topic_name}-value"