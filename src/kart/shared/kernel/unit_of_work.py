"""The Unit of Work a use case runs its changes in, without knowing what stores them."""

from collections.abc import Callable
from contextlib import AbstractContextManager

# Each call starts one transaction. Its block gets the repository `R`, bound to that transaction,
# and the transaction commits when the block succeeds and rolls back when it raises.
type UnitOfWork[R] = Callable[[], AbstractContextManager[R]]
