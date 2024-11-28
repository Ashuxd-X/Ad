import asyncio
import io
import random
import sys
import traceback
from datetime import datetime
from random import choice, randint
from time import time
from typing import Dict, List, NoReturn
from uuid import uuid4

import aiohttp
import cv2
import numpy as np
from aiohttp_socks import ProxyConnector
from PIL import Image
from pyrogram.client import Client

from bot.config.config import settings
from bot.core.canvas_updater.dynamic_canvas_renderer import DynamicCanvasRenderer
from bot.core.canvas_updater.websocket_manager import WebSocketManager
from bot.core.notpx_api_checker import NotPXAPIChecker
from bot.core.tg_mini_app_auth import TelegramMiniAppAuth
from bot.utils.json_manager import JsonManager
from bot.utils.logger import dev_logger, logger


class NotPXBot:
    RETRY_ITERATION_DELAY = 10 * 60  # 10 minutes
    RETRY_DELAY = 5  # 5 seconds

    def __init__(
        self, telegram_client: Client, websocket_manager: WebSocketManager
    ) -> None:
        self.telegram_client: Client = telegram_client
        self.session_name: str = telegram_client.name
        self.websocket_manager: WebSocketManager = websocket_manager
        self._headers = self._create_headers()
        self.template_id: int = 0  # defined in _set_template
        self.template_url: str = ""  # defined in _set_template
        self.template_x: int = 0  # defined in _set_template
        self.template_y: int = 0  # defined in _set_template
        self.template_size: int = 0  # defined in _set_template
        self.balance = 0  # Initialize balance
        self.max_boosts: Dict[str, int] = {
            "paintReward": 7,
            "reChargeSpeed": 11,
            "energyLimit": 7,
        }
        self.boost_prices: Dict[str, Dict[int, int]] = {
            "paintReward": {2: 5, 3: 100, 4: 200, 5: 300, 6: 500, 7: 600},
            "reChargeSpeed": {
                2: 5,
                3: 100,
                4: 200,
                5: 300,
                6: 400,
                7: 500,
                8: 600,
                9: 700,
                10: 800,
                11: 900,
            },
            "energyLimit": {2: 5, 3: 100, 4: 200, 5: 300, 6: 400, 7: 10},
        }
        self._canvas_renderer: DynamicCanvasRenderer = DynamicCanvasRenderer()
        self._tasks_list: Dict[str, Dict[str, str]] = {
            "x_tasks_list": {
                "x:notpixel": "notpixel",
                "x:notcoin": "notcoin",
            },
            "channel_tasks_list": {
                "channel:notpixel_channel": "notpixel_channel",
                "channel:notcoin": "notcoin",
            },
            "league_tasks_list": {
                "leagueBonusSilver": "leagueBonusSilver",
                "leagueBonusGold": "leagueBonusGold",
                "leagueBonusPlatinum": "leagueBonusPlatinum",
            },
            "click_tasks_list": {},
        }
        self._tasks_to_complete: Dict[str, Dict[str, str]] = {}
        self._league_weights: Dict[str, int] = {
            "bronze": 0,
            "silver": 1,
            "gold": 2,
            "platinum": 3,
        }
        self._quests_list: List[str] = [
            "secretWord:happy halloween",
        ]
        self._quests_to_complete: List[str] = []
        self._notpx_api_checker: NotPXAPIChecker = NotPXAPIChecker()

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

        websocket_headers = {
            "Cache-Control": "no-cache",
            "Pragma": "no-cache",
            "Sec-Fetch-Dest": "websocket",
            "Sec-Fetch-Mode": "websocket",
            "Sec-Fetch-Site": "same-site",
        }

        def create_headers(additional_headers=None):
            headers = base_headers.copy()
            if additional_headers:
                headers.update(additional_headers)
            return headers

        return {
            "notpx": create_headers({"Authorization": ""}),
            "tganalytics": create_headers(),
            "plausible": create_headers({"Sec-Fetch-Site": "cross-site"}),
            "websocket": create_headers(websocket_headers),
            "image_notpx": create_headers(),
        }

    async def run(self, user_agent: str, proxy: str | None) -> NoReturn:
        for header in self._headers.values():
            header["User-Agent"] = user_agent

        self.proxy = proxy

        while True:
            try:
                proxy_connector = ProxyConnector().from_url(proxy) if proxy else None
                async with aiohttp.ClientSession(connector=proxy_connector) as session:
                    # Add the ad-watching feature here
                    if settings.WATCH_ADS:
                        await self._watch_ads(session)

                    # Existing workflows continue here.
                    # For example: task handling, painting, claiming rewards.
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

    # Rest of the existing methods in NotPXBot remain unchanged.
