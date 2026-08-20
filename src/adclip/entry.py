"""Installed adclip CLI entry point.

The legacy command group remains in :mod:`adclip.cli`; new standalone product
surfaces are composed here so transport-neutral application code stays separate
from Click wiring.
"""

from adclip.brand_cli import brand_group
from adclip.cli import main
from adclip.storage.cli import storage_group

main.add_command(brand_group)
main.add_command(storage_group)

__all__ = ["main"]
