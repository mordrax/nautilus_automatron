"""One-time migration: copy bar data and instruments into ParquetDataCatalog format.

Usage:
    cd packages/runner
    uv run python -m runner.migrate /path/to/backtest_catalog
"""

import sys
from pathlib import Path

import pyarrow.ipc as ipc

from nautilus_trader.model.data import Bar
from nautilus_trader.persistence.catalog import ParquetDataCatalog
from nautilus_trader.serialization.arrow.serializer import ArrowSerializer


def _make_xauusd(venue_str: str, symbol_str: str = "XAUUSD"):
    """Create XAUUSD instrument definition for a given venue."""
    from decimal import Decimal
    from nautilus_trader.model.identifiers import InstrumentId, Symbol, Venue
    from nautilus_trader.model.instruments import CurrencyPair
    from nautilus_trader.model.objects import Currency, Price, Quantity

    venue = Venue(venue_str)
    return CurrencyPair(
        instrument_id=InstrumentId(Symbol(symbol_str), venue),
        raw_symbol=Symbol(symbol_str),
        base_currency=Currency.from_str("XAU"),
        quote_currency=Currency.from_str("USD"),
        price_precision=2,
        size_precision=0,
        price_increment=Price.from_str("0.01"),
        size_increment=Quantity.from_int(1),
        lot_size=None,
        max_quantity=None,
        min_quantity=Quantity.from_int(1),
        max_price=None,
        min_price=None,
        margin_init=Decimal("0.03"),
        margin_maint=Decimal("0.03"),
        maker_fee=Decimal("0.00002"),
        taker_fee=Decimal("0.00002"),
        ts_event=0,
        ts_init=0,
    )


# Instruments matching the bar data's instrument IDs
INSTRUMENTS = [
    _make_xauusd("IBCFD", "XAUUSD"),  # Matches XAUUSD.IBCFD in bar data
]


def migrate_catalog(catalog_path: str) -> None:
    """Migrate bar data from backtest/ into data/ and write instrument definitions."""
    root = Path(catalog_path)
    catalog = ParquetDataCatalog(str(root))

    # 1. Write instrument definitions
    for instrument in INSTRUMENTS:
        catalog.write_data([instrument])
        print(f"Wrote instrument: {instrument.id}")

    # 2. Find and migrate bar data from backtest runs
    backtest_dir = root / "backtest"
    if not backtest_dir.exists():
        print("No backtest/ directory found")
        return

    seen_bar_types: set[str] = set()

    for run_dir in sorted(backtest_dir.iterdir()):
        if not run_dir.is_dir():
            continue
        bar_dir = run_dir / "bar"
        if not bar_dir.exists():
            continue

        for bar_type_dir in bar_dir.iterdir():
            if not bar_type_dir.is_dir():
                continue
            bar_type_name = bar_type_dir.name
            if bar_type_name in seen_bar_types:
                continue  # Already migrated this bar type

            # Read all feather files for this bar type
            all_bars: list[Bar] = []
            for feather_file in sorted(bar_type_dir.glob("*.feather")):
                with open(feather_file, "rb") as f:
                    reader = ipc.open_stream(f)
                    table = reader.read_all()
                bars = ArrowSerializer.deserialize(Bar, table)
                all_bars.extend(bars)

            if all_bars:
                # Sort by timestamp (required by write_data)
                all_bars.sort(key=lambda b: b.ts_init)
                catalog.write_data(all_bars)
                seen_bar_types.add(bar_type_name)
                print(f"Migrated {len(all_bars)} bars for {bar_type_name}")

    print(f"\nMigration complete. {len(seen_bar_types)} bar types migrated.")
    print(f"Data written to: {root / 'data'}")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print(f"Usage: python -m runner.migrate <catalog_path>")
        sys.exit(1)
    migrate_catalog(sys.argv[1])
