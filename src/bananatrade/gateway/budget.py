class BudgetExceededError(RuntimeError):
    """Raised before a call that would exceed the daily budget."""


class BudgetGuard:
    def __init__(self, daily_limit: float) -> None:
        self.daily_limit = daily_limit
        self.spent = 0.0

    def check(self, estimate: float) -> None:
        if self.spent + estimate > self.daily_limit:
            raise BudgetExceededError("Daily budget exceeded")

    def record(self, cost: float) -> None:
        self.spent += cost
