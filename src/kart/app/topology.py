"""Declares Kart's RabbitMQ topology: `python -m kart.app.topology`.

Declaring what already exists is a no-op, so Compose runs it on every `up`, before Debezium
Server publishes to the exchange.
"""

import pika

from kart.app.settings import Settings

# Every integration event is published here, routed by its type (for example
# `order.confirmed.v1`). Debezium Server names it too: deploy/debezium/application.properties.
EVENTS_EXCHANGE = "kart.events"


def declare_topology(rabbitmq_url: str) -> None:
    connection = pika.BlockingConnection(pika.URLParameters(rabbitmq_url))
    try:
        connection.channel().exchange_declare(EVENTS_EXCHANGE, exchange_type="topic", durable=True)
    finally:
        connection.close()


if __name__ == "__main__":
    declare_topology(Settings().rabbitmq_url)
