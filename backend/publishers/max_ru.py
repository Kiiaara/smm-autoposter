from publishers.base import PublishResult

SETUP_GUIDE = (
    "Max (max.ru) posting is not yet implemented.\n"
    "The platform's public API is limited - manual posting is required for now."
)


async def publish_to_max(*args, **kwargs) -> PublishResult:
    return PublishResult(ok=False, error=SETUP_GUIDE)
