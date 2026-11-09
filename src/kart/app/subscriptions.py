"""Every context's subscription: `rabbitmq_setup` declares their queues and the `worker`
consumes them.

None subscribes to anything yet.
"""

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from kart.building_blocks.inbox import Subscription

SUBSCRIPTIONS: tuple[Subscription, ...] = ()
