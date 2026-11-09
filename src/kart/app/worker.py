"""The `worker` process: consumes every context's subscription (ADR-0004)."""

import logging
from functools import partial
from typing import TYPE_CHECKING, cast

import pika

from kart.app.background_process import run_until_stopped
from kart.app.database import create_database_engine, unit_of_work
from kart.app.subscriptions import SUBSCRIPTIONS
from kart.building_blocks.inbox import record_in_inbox
from kart.shared_kernel.event_envelope import EventEnvelope

if TYPE_CHECKING:
    import threading
    from collections.abc import Collection

    from pika.adapters.blocking_connection import BlockingChannel
    from pika.spec import Basic, BasicProperties
    from sqlalchemy import Engine

    from kart.app.settings import Settings
    from kart.building_blocks.inbox import Subscription

_logger = logging.getLogger(__name__)
# How many deliveries an event gets: if the last one fails too, it goes to the dead-letter queue.
ATTEMPTS = 5
# How long to wait for messages before checking whether to stop.
_POLL_SECONDS = 0.2


def consume(
    rabbitmq_url: str,
    engine: Engine,
    subscriptions: Collection[Subscription],
    stopped: threading.Event,
) -> None:
    """Hand each event on the subscriptions' queues to its handler, until `stopped` is set."""
    if not subscriptions:  # nothing to consume, so no need for the broker
        stopped.wait()
        return
    connection = pika.BlockingConnection(pika.URLParameters(rabbitmq_url))
    try:
        channel = connection.channel()
        # One event at a time, so a queue's events are handled in the order they arrive.
        channel.basic_qos(prefetch_count=1)
        for subscription in subscriptions:
            channel.basic_consume(subscription.queue, partial(_handle, engine, subscription))
        while not stopped.is_set():
            connection.process_data_events(time_limit=_POLL_SECONDS)
    finally:
        connection.close()


def _handle(  # noqa: PLR0913, PLR0917 pika's four callback arguments, after two of ours
    engine: Engine,
    subscription: Subscription,
    channel: BlockingChannel,
    method: Basic.Deliver,
    properties: BasicProperties,
    body: bytes,
) -> None:
    """Handle one event in a unit of work, and acknowledge it only once that commits.

    If anything fails, the event goes back on the queue to be retried, or to the dead-letter
    queue once it has been delivered `ATTEMPTS` times. That includes an event that can never
    be handled, such as one with no handler for its type.
    """
    # pika types it optional, but every delivery has one.
    delivery_tag = cast("int", method.delivery_tag)
    try:
        event = EventEnvelope.from_json(body.decode())
        with unit_of_work(engine, subscription.context) as session:
            if record_in_inbox(session, event.event_id):
                subscription.handlers[event.type](session, event)
    except Exception:
        _logger.exception(
            "%s failed to handle a message from %s", subscription.context, subscription.queue
        )
        # The quorum queue counts the earlier deliveries in this header.
        attempts = 1 + int((properties.headers or {}).get("x-acquired-count", 0))
        channel.basic_nack(delivery_tag, requeue=attempts < ATTEMPTS)
    else:
        channel.basic_ack(delivery_tag)


def _consume_every_subscription(settings: Settings, stopped: threading.Event) -> None:
    engine = create_database_engine(settings.database_url)
    try:
        consume(settings.rabbitmq_url, engine, SUBSCRIPTIONS, stopped)
    finally:
        engine.dispose()


if __name__ == "__main__":
    run_until_stopped("worker", _consume_every_subscription)
