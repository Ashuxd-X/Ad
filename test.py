import asyncio
import aiohttp
import random
from pyrogram.client import Client
from bot.utils.logger import logger
from bot.config.config import settings
from aiohttp_socks import ProxyConnector
from typing import Dict, NoReturn

class NotPXBot:
    RETRY_ITERATION_DELAY = 10 * 60  # 10 minutes
    RETRY_DELAY = 5  # 5 seconds

    def __init__(self, telegram_client: Client, websocket_manager):
        self.telegram_client = telegram_client
        self.session_name = telegram_client.name
        self.websocket_manager = websocket_manager
        self._headers = self._create_headers()
        self.balance = 0  # Initialize balance for updates after ad-watching

    def _create_headers(self) -> Dict[str, Dict[str, str]]:
        base_headers = {
            "Accept-Language": "en-US,en;q=0.9",
            "Origin": "https://app.notpx.app",
            "Referer": "https://app.notpx.app/",
            "Sec-Fetch-Dest": "empty",
            "Sec-Fetch-Mode": "cors",
            "Sec-Fetch-Site": "same-site",
            "User-Agent": "",
        }
        return {"notpx": base_headers}

    async def run(self, user_agent: str, proxy: str | None) -> NoReturn:
        """
        Main loop for the bot, handles session and tasks.
        """
        self.proxy = proxy
        for header in self._headers.values():
            header["User-Agent"] = user_agent

        while True:
            try:
                proxy_connector = ProxyConnector().from_url(proxy) if proxy else None
                async with aiohttp.ClientSession(connector=proxy_connector) as session:
                    if settings.WATCH_ADS:
                        await self._watch_ads(session)

                    # Add other workflows here as needed.
                    logger.info(f"{self.session_name} | Sleeping before next iteration.")
                    await asyncio.sleep(random.randint(5, 10) * 60)  # Sleep 5-10 mins
            except Exception as error:
                logger.error(f"{self.session_name} | Error occurred: {error}")
                await asyncio.sleep(self.RETRY_ITERATION_DELAY)

    async def _watch_ads(self, http_client: aiohttp.ClientSession):
        """
        Watch ads and claim rewards.
        """
        logger.info(f"{self.session_name} | Starting ad-watching loop.")
        headers = self._headers["notpx"]
        base_url = "https://notpx.app/api/v1/ads"

        try:
            while True:
                # Step 1: Fetch ad information
                response = await http_client.get(base_url, headers=headers)
                if response.status == 200:
                    ad_data = await response.json()
                    render_url = ad_data['banner']['trackings'][0]['value']
                    show_url = ad_data['banner']['trackings'][1]['value']
                    reward_url = ad_data['banner']['trackings'][4]['value']

                    # Step 2: Render ad
                    await http_client.get(render_url, headers=headers)
                    logger.info(f"{self.session_name} | Ad render tracked.")

                    # Step 3: Simulate viewing the ad
                    await asyncio.sleep(10)  # Simulate watching ad

                    # Step 4: Track ad as shown
                    await http_client.get(show_url, headers=headers)
                    logger.info(f"{self.session_name} | Ad show tracked.")

                    # Step 5: Claim reward
                    reward_response = await http_client.get(reward_url, headers=headers)
                    reward_response.raise_for_status()
                    reward_data = await reward_response.json()
                    reward_amount = reward_data.get("reward", 0)
                    self.balance += reward_amount  # Update bot's balance
                    logger.info(f"{self.session_name} | Ad reward claimed: {reward_amount} PX.")

                else:
                    logger.info(f"{self.session_name} | No ads available, exiting loop.")
                    break
        except Exception as error:
            logger.error(f"{self.session_name} | Error watching ads: {error}")

    # Other existing methods in NotPXBot would remain here.
