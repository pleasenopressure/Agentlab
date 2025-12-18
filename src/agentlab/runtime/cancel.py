
import asyncio

class CancellationToken:
    """
    协作式取消：长任务中定期 checkpoint()，一旦取消就抛 CancelledError。
    """
    def __init__(self):
        self._ev = asyncio.Event()

    def cancel(self) -> None:
        self._ev.set()

    @property
    def cancelled(self) -> bool:
        return self._ev.is_set()

    async def checkpoint(self) -> None:
        if self.cancelled:
            raise asyncio.CancelledError("Cancelled by user")
