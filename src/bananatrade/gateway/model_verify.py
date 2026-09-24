import logging


class ModelMismatchError(RuntimeError):
    """Raised when the router returns an unexpected model."""


def verify_model(tier: str, configured: str, actual: str, aliases: list[str]) -> None:
    if actual == configured or actual in aliases:
        return
    message = "Model mismatch for %s: expected %s, received %s"
    if tier in {"tier3_strategist", "tier4_cio"}:
        raise ModelMismatchError(message % (tier, configured, actual))
    logging.getLogger(__name__).warning(message, tier, configured, actual)
