import subprocess
import sys
import textwrap
from pathlib import Path

from kart.shared.kernel.ids import OrderId

TY = Path(sys.executable).with_name("ty")


def test_a_new_id_is_a_uuid7() -> None:
    assert OrderId.new().version == 7


def test_an_id_made_later_sorts_later() -> None:
    first, second = OrderId.new(), OrderId.new()

    assert first < second


def ty_accepts(tmp_path: Path, source: str) -> bool:
    module = tmp_path / "uses_ids.py"
    module.write_text(textwrap.dedent(source))
    result = subprocess.run(  # noqa: S603
        [TY, "check", "--python", sys.prefix, "--no-progress", str(module)],
        capture_output=True,
        text=True,
        check=False,
        cwd=tmp_path,
    )
    assert "error[unresolved-import]" not in result.stdout, result.stdout
    return result.returncode == 0


USES_AN_ORDER_ID = """
    from kart.shared.kernel.ids import AccountId, OrderId

    def cancel(order_id: OrderId) -> None: ...

    cancel({argument})
"""


def test_an_order_id_is_accepted_where_an_order_id_is_expected(tmp_path: Path) -> None:
    assert ty_accepts(tmp_path, USES_AN_ORDER_ID.format(argument="OrderId.new()"))


def test_an_account_id_is_rejected_where_an_order_id_is_expected(tmp_path: Path) -> None:
    assert not ty_accepts(tmp_path, USES_AN_ORDER_ID.format(argument="AccountId.new()"))
