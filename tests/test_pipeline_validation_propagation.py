import asyncio

import pytest
from pydantic import ValidationError

from bananatrade.orchestration.pipeline import run_agents


class BugAgent:
    name = "bug"
    tier = "tier1_fast"
    prompt_version = "bug.v1"

    async def run(self, snapshot):
        raise ValidationError.from_exception_data("internal", [])


def test_internal_validation_error_propagates() -> None:
    with pytest.raises(ValidationError):
        asyncio.run(run_agents([BugAgent()], {}))
