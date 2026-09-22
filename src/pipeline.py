import logging
from datetime import datetime
from zoneinfo import ZoneInfo

from .finviz_client import FinvizClient
from .models import FilterDefinition
from .storage import Storage


LOGGER = logging.getLogger(__name__)


def run_scan(client: FinvizClient, storage: Storage, filters: list[FilterDefinition], timezone_name: str) -> dict:
    timezone = ZoneInfo(timezone_name)
    run_id = storage.start_run(filters, datetime.now(timezone), timezone_name)
    LOGGER.info("Starting run %d: %d filters", run_id, len(filters))
    try:
        for position, definition in enumerate(filters, start=1):
            LOGGER.info("Filter %d/%d: %s", position, len(filters), definition.name)
            try:
                stocks = client.scrape_filter(definition)
            except Exception as error:
                LOGGER.exception("%s failed; continuing with remaining filters", definition.name)
                storage.fail_filter(run_id, definition.name, str(error))
                continue
            storage.save_filter(run_id, definition.name, stocks)
    except BaseException:
        storage.finish_run(run_id, datetime.now(timezone), interrupted=True)
        raise
    snapshot = storage.finish_run(run_id, datetime.now(timezone))
    LOGGER.info("Run %d: %s, %d unique tickers", run_id, snapshot["run"]["status"], len(snapshot["stocks"]))
    return snapshot
