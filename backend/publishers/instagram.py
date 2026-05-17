from publishers.base import PublishResult

SETUP_GUIDE = (
    "Instagram posting requires Meta Business API setup:\n"
    "1. Create a Meta Developer App at developers.facebook.com\n"
    "2. Link a Facebook Page to an Instagram Business Account\n"
    "3. Get instagram_content_publish permission\n"
    "4. Generate a long-lived Page Access Token\n"
    "5. Add page_id and access_token in channel settings"
)


async def publish_to_instagram(*args, **kwargs) -> PublishResult:
    return PublishResult(ok=False, error=SETUP_GUIDE)
