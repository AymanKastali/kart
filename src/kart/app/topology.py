"""Declares Kart's RabbitMQ topology: `python -m kart.app.topology`.

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

    from kart.building_blocks.inbox import Subscription

# Every integration event is published here, routed by its type (for example
# `order.confirmed.v1`). Debezium Server names it too: deploy/debezium/application.properties.
EVENTS_EXCHANGE = "kart.events"
_QUORUM_QUEUE = {"x-queue-type": "quorum"}


def declare_topology(
    rabbitmq_url: str, subscriptions: Iterable[Subscription] = SUBSCRIPTIONS
) -> None:
    connection = pika.BlockingConnection(pika.URLParameters(rabbitmq_url))
    try:
        channel = connection.channel()
        channel.exchange_declare(EVENTS_EXCHANGE, exchange_type="topic", durable=True)
        for subscription in subscriptions:
            # An event the worker gives up on goes to the dead-letter queue, through the
            # default exchange, which routes by queue name. Quorum queues count deliveries.
            # Their arguments are fixed once declared (ADR-0010).
            channel.queue_declare(
                subscription.dead_letter_queue,
                durable=True,
                arguments=_QUORUM_QUEUE,
            )
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
    finally:
        connection.close()


if __name__ == "__main__":
    declare_topology(Settings().rabbitmq_url)
