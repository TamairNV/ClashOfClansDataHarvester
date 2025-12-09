import coc
import asyncio


def get_valid_token(email, password):
    """
    Uses coc.py to login, fix the IP address on the developer portal,
    and return a valid API token string.
    """

    async def fetch():
        # Use 'async with' to ensure the client always closes cleanly
        async with coc.Client() as client:

            await client.login(email, password)

            http = client.http
            if hasattr(http, 'keys'):
                return next(http.keys)

            raise Exception("Login successful, but no API keys found.")

    # Run the async function synchronously
    return asyncio.run(fetch())