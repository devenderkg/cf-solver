"""
Cloudflare Challenge Solver Library
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

A professional Python library designed to automate the resolution of Cloudflare's 
interactive and non-interactive challenges using the zendriver browser automation core.

:copyright: (c) 2026 by Devender Gupta.
:license: MIT, see LICENSE for more details.
"""

import asyncio
import random
import json
from pathlib import Path
from enum import Enum
from typing import Optional, List, Any, Iterable, Dict, Tuple
from dataclasses import dataclass
from datetime import datetime

import latest_user_agents
import user_agents
import zendriver
from zendriver import cdp
from zendriver.cdp.emulation import UserAgentBrandVersion, UserAgentMetadata
from zendriver.core.element import Element

def get_chrome_user_agent() -> str:
    """
    Retrieves a random, high-quality Chrome User-Agent string from the latest 
    user-agent database. Filters specifically for Chrome to ensure compatibility 
    with core automation logic.

    Returns:
        str: A randomly selected Chrome User-Agent string.
    """
    chrome_user_agents = [
        ua for ua in latest_user_agents.get_latest_user_agents()
        if "Chrome" in ua and "Edg" not in ua
    ]
    return random.choice(chrome_user_agents)

class ChallengePlatform(Enum):
    """
    Enumeration of known Cloudflare challenge interaction types.
    Matches the 'cType' signature found in Cloudflare's challenge HTML payload.
    """
    JAVASCRIPT = "non-interactive"
    MANAGED = "managed"
    INTERACTIVE = "interactive"

class CloudflareSolver:
    """
    Main entry point for solving Cloudflare challenges.
    
    This class handles browser orchestration, challenge detection, and interaction
    logic. It uses zendriver for high-performance, asynchronous browser control.

    Example:
        >>> async with CloudflareSolver() as solver:
        >>>     cookies, ua = await solver.solve("https://example.com")
    """
    
    def __init__(
        self, 
        user_agent: Optional[str] = None, 
        timeout: float = 30, 
        headless: bool = True
    ):
        """
        Initializes the solver with browser configuration.

        Args:
            user_agent (Optional[str]): Custom UA string. If None, a random Chrome UA is generated.
            timeout (float): Maximum seconds to wait for a challenge to be solved.
            headless (bool): Whether to run the browser in headless mode.
        """
        self.user_agent = user_agent or get_chrome_user_agent()
        config = zendriver.Config(headless=headless)
        
        # We set the initial UA here, but we also override via CDP for deeper stealth
        config.add_argument(f"--user-agent={self.user_agent}")
        
        self.driver = zendriver.Browser(config)
        self._timeout = timeout

    async def __aenter__(self):
        """Asynchronous context manager entry."""
        await self.driver.start()
        return self

    async def __aexit__(self, *_: Any):
        """Asynchronous context manager exit, ensuring browser shutdown."""
        await self.driver.stop()

    async def get_cookies(self) -> List[Dict]:
        """
        Fetches all cookies current held by the browser instance.

        Returns:
            List[Dict]: A list of cookie objects in standard JSON-serializable format.
        """
        cookies = await self.driver.cookies.get_all()
        return [cookie.to_json() for cookie in cookies]

    def extract_clearance_cookie(self, cookies: Iterable[dict]) -> Optional[dict]:
        """
        Filters a list of cookies to find the specific Cloudflare clearance token.

        Args:
            cookies (Iterable[dict]): Browser cookies.

        Returns:
            Optional[dict]: The 'cf_clearance' cookie if found, otherwise None.
        """
        for cookie in cookies:
            if cookie["name"] == "cf_clearance":
                return cookie
        return None

    async def get_current_user_agent(self) -> str:
        """
        Queries the browser's JavaScript environment for the effective User-Agent.

        Returns:
            str: The value of navigator.userAgent.
        """
        return await self.driver.main_tab.evaluate("navigator.userAgent")

    async def set_user_agent_metadata(self, user_agent: str):
        """
        Deeply overrides User-Agent metadata using Chrome DevTools Protocol (CDP).
        
        This prevents detection from Client Hints and other metadata-based 
        anti-bot checks by aligning the navigator.userAgentData with the 
        provided UA string.

        Args:
            user_agent (str): The target User-Agent string to emulate.
        """
        device = user_agents.parse(user_agent)
        
        # Construct metadata based on parsed user agent version
        browser_major_version = str(device.browser.version[0])
        
        metadata = UserAgentMetadata(
            architecture="x86",
            bitness="64",
            brands=[
                UserAgentBrandVersion(brand="Not)A;Brand", version="8"),
                UserAgentBrandVersion(brand="Chromium", version=browser_major_version),
                UserAgentBrandVersion(brand="Google Chrome", version=browser_major_version),
            ],
            full_version_list=[
                UserAgentBrandVersion(brand="Not)A;Brand", version="8"),
                UserAgentBrandVersion(brand="Chromium", version=browser_major_version),
                UserAgentBrandVersion(brand="Google Chrome", version=browser_major_version),
            ],
            mobile=device.is_mobile,
            model=device.device.model or "",
            platform=device.os.family,
            platform_version=device.os.version_string,
            full_version=device.browser.version_string,
            wow64=False,
        )
        
        # Apply the override at the network layer via CDP
        self.driver.main_tab.feed_cdp(
            cdp.network.set_user_agent_override(user_agent, user_agent_metadata=metadata)
        )

    async def detect_challenge(self) -> Optional[ChallengePlatform]:
        """
        Analyzes the current page source for Cloudflare challenge markers.

        Returns:
            Optional[ChallengePlatform]: The detected challenge type or None if none found.
        """
        html = await self.driver.main_tab.get_content()
        for platform in ChallengePlatform:
            # Cloudflare injected JS typically contains cType: '...'
            if f"cType: '{platform.value}'" in html:
                return platform
        return None

    async def solve_challenge(self):
        """
        Core interaction loop for solving the detected challenge.
        
        This method looks for the Turnstile widget inside shadow roots and 
        performs human-like mouse interactions to satisfy the prompt.
        """
        start_timestamp = datetime.now()
        
        while (
            self.extract_clearance_cookie(await self.get_cookies()) is None
            and await self.detect_challenge() is not None
            and (datetime.now() - start_timestamp).seconds < self._timeout
        ):
            # Locate the Turnstile challenge input
            widget_input = await self.driver.main_tab.find("input")
            
            # Navigate into shadow roots where the actual checkbox lives
            if not widget_input or widget_input.parent is None or not widget_input.parent.shadow_roots:
                await asyncio.sleep(0.5)
                continue

            # Create an element wrapper for the shadow root content
            challenge_wrapper = Element(
                widget_input.parent.shadow_roots[0],
                self.driver.main_tab,
                widget_input.parent.tree,
            )
            
            # The actual clickable area is usually the first child of the shadow root
            challenge = challenge_wrapper.children[0]

            if isinstance(challenge, Element) and "display: none;" not in challenge.attrs.get("style", ""):
                await asyncio.sleep(1)
                try:
                    # Move mouse to position and click
                    await challenge.get_position()
                    await challenge.mouse_click()
                except Exception:
                    # Retry logic handled by the while loop
                    continue
                    
            await asyncio.sleep(0.5)

    async def solve(self, url: str, force_refresh: bool = False) -> Tuple[List[Dict], str]:
        """ 
        The high-level method to navigate to a URL and ensure a Cloudflare session.
        
        If a challenge is detected, it will attempt to solve it automatically.
        
        Args:
            url (str): The target URL protected by Cloudflare.
            force_refresh (bool): If True, clears existing cookies before navigation.

        Returns:
            Tuple[List[Dict], str]: A tuple containing the list of cookies and the User-Agent.
        """
        if force_refresh:
            await self.driver.cookies.clear()
            
        await self.driver.get(url)
        
        all_cookies = await self.get_cookies()
        clearance = self.extract_clearance_cookie(all_cookies)

        # If no clearance, trigger solving logic
        if clearance is None or force_refresh:
            current_ua = await self.get_current_user_agent()
            
            # Align metadata for stealth
            await self.set_user_agent_metadata(current_ua)
            
            # Attempt to solve if a challenge platform is actually detected
            challenge_platform = await self.detect_challenge()
            if challenge_platform:
                await self.solve_challenge()
            
            # Re-fetch final cookies
            all_cookies = await self.get_cookies()

        return all_cookies, self.user_agent

    @staticmethod
    def to_cookie_dict(cookies: List[Dict]) -> Dict[str, str]:
        """
        Utility to convert complex cookie objects into simple key-value pairs.
        Compatible with httpx.AsyncClient and requests.Session.
        """
        return {c["name"]: c["value"] for c in cookies}

    @staticmethod
    def to_cookie_string(cookies: List[Dict]) -> str:
        """
        Utility to format cookies as a single 'Cookie' header string.
        """
        return "; ".join([f"{c['name']}={c['value']}" for c in cookies])

    @staticmethod
    def save_to_json(path: str, cookies: List[Dict], user_agent: str):
        """
        Persists a session's cookies and User-Agent to a JSON file.
        """
        data = {
            "user_agent": user_agent,
            "cookies": cookies
        }
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=4)

    @staticmethod
    def load_from_json(path: str) -> Tuple[List[Dict], str]:
        """
        Loads a previously saved session from a JSON file.
        """
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data["cookies"], data["user_agent"]
