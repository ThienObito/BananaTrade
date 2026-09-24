class GatewayError(RuntimeError):
    """Base class for gateway failures."""


class GatewayAuthError(GatewayError):
    pass


class ModelNotAvailableError(GatewayError):
    pass


class GatewayConnectionError(GatewayError):
    pass


class EmptyCompletionError(GatewayError):
    pass
