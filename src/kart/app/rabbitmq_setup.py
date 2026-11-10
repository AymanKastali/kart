"""Sets up Kart's RabbitMQ exchange and queues: `python -m kart.app.rabbitmq_setup`.

Declaring what already exists is a no-op, so Compose runs it on every `up`, before Debezium
Server publishes to the exchange. A subscribing context's queue therefore exists before the
first event it binds to is published.
"""

from typing import TYPE_CHECKING

import pika

from kart.app.settings import Settings
from kart.app.subscriptions import SUBSCRIPTIONS

if TYPE_CHECKING:
    from collections.abc import Iterable

    from pika.adapters.blocking_connection import BlockingChannel

    from kart.shared.inbox import Subscription

# Every integration event is published here, routed by its type (for example
# `order.confirmed.v1`). Debezium Server names it too: debezium/application.properties.
EVENTS_EXCHANGE = "kart.events"
_QUORUM_QUEUE = {"x-queue-type": "quorum"}


def set_up_rabbitmq(
    rabbitmq_url: str, subscriptions: Iterable[Subscription] = SUBSCRIPTIONS
) -> None:
    connection = pika.BlockingConnection(pika.URLParameters(rabbitmq_url))
    try:
        channel = connection.channel()
        channel.exchange_declare(EVENTS_EXCHANGE, exchange_type="topic", durable=True)
        for subscription in subscriptions:
            _declare_queues(channel, subscription)
    finally:
        connection.close()


def _declare_queues(channel: BlockingChannel, subscription: Subscription) -> None:
    """The subscription's queue, bound to its event types, and its dead-letter queue."""
    # An event the worker gives up on goes to the dead-letter queue, through the default
    # exchange, which routes by queue name. Quorum queues count deliveries. Their arguments
    # are fixed once declared (ADR-0010).
    channel.queue_declare(subscription.dead_letter_queue, durable=True, arguments=_QUORUM_QUEUE)
    channel.queue_declare(
        subscription.queue,
        durable=True,
        arguments={
            **_QUORUM_QUEUE,
            "x-dead-letter-exchange": "",
            "x-dead-letter-routing-key": subscription.dead_letter_queue,
        },
    )
    for event_type in subscription.handlers:
        channel.queue_bind(subscription.queue, EVENTS_EXCHANGE, event_type)


if __name__ == "__main__":
    set_up_rabbitmq(Settings().rabbitmq_url)
