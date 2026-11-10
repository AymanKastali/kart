"""Ids shared across contexts. Each is its own type, so passing one where another is expected
fails type checking."""

from typing import Self
from uuid import UUID, uuid7


class _Id(UUID):
    __slots__ = ()

    @classmethod
    def new(cls) -> Self:
        """A new id, time ordered (UUIDv7)."""
        return cls(int=uuid7().int)


class AccountId(_Id):
    __slots__ = ()


class SellerId(_Id):
    __slots__ = ()


class OrderId(_Id):
    __slots__ = ()
