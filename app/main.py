"""CLI entrypoint for Idea Canvas."""

from __future__ import annotations

import logging
from pathlib import Path

import click
import uvicorn

from .app import create_app
from .config import get_default_config_path, load_config


@click.command()
@click.option(
    "-c",
    "--config",
    "config_path",
    default=None,
    type=click.Path(path_type=Path),
    help="Config file path",
)
@click.option("-v", "--verbose", is_flag=True, help="Enable verbose logging")
def main(config_path: Path | None, verbose: bool) -> None:
    """Run the Idea Canvas FastAPI app."""
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
    )

    chosen_path = config_path or get_default_config_path()
    config = load_config(chosen_path)

    app = create_app(config)
    uvicorn.run(
        app,
        host=config.web.host,
        port=config.web.port,
        log_level="debug" if verbose else "info",
    )


if __name__ == "__main__":
    main()
