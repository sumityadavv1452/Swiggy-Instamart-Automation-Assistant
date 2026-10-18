"""
Swiggy Instamart Automation Backend Module.
Provides programmatic control over an active, authenticated Chrome browser session
via Chrome DevTools Protocol (CDP) and Playwright.
"""

import os
import sys
import asyncio
import re
from typing import Dict, Any, List, Optional
from dotenv import load_dotenv
from playwright.async_api import async_playwright, Browser, Page

load_dotenv()

if sys.stdout and hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

CHROME_CDP_URL = os.getenv("CHROME_CDP_URL", "http://127.0.0.1:9222")
FREE_DELIVERY_THRESHOLD = int(os.getenv("FREE_DELIVERY_THRESHOLD", "99"))
DEFAULT_PAYMENT_MODE = os.getenv("DEFAULT_PAYMENT_MODE", "cod")
DEFAULT_UPI_ID = os.getenv("UPI_ID", "")
ADDRESS_TAG = os.getenv("ADDRESS_TAG", "WORK")


async def get_swiggy_page(p) -> tuple[Browser, Page]:
    """
    Connects to the Chrome session over CDP and retrieves or activates
    the Swiggy Instamart page.
    """
    try:
        browser = await p.chromium.connect_over_cdp(CHROME_CDP_URL)
    except Exception:
        # Fallback to localhost if 127.0.0.1 differs in local DNS configuration
        fallback_url = "http://localhost:9222" if "127.0.0.1" in CHROME_CDP_URL else "http://127.0.0.1:9222"
        browser = await p.chromium.connect_over_cdp(fallback_url)

    context = browser.contexts[0] if browser.contexts else await browser.new_context()
    swiggy_pages = [pg for pg in context.pages if "swiggy.com" in pg.url]
    
    if swiggy_pages:
        page = swiggy_pages[0]
    elif context.pages:
        page = context.pages[0]
    else:
        page = await context.new_page()

    await page.bring_to_front()
    return browser, page


async def add_item_to_cart(page: Page, item_name: str, quantity: int = 1) -> bool:
    """
    Directly navigates to Instamart search query and adds the item to cart.
    Handles variant selection drawers automatically.
    """
    encoded_item = item_name.strip()
    search_url = f"https://www.swiggy.com/instamart/search?custom_back=true&query={encoded_item}"
    await page.goto(search_url, wait_until="domcontentloaded", timeout=30000)
    await page.wait_for_timeout(1500)

    # Locate first available item card add button
    add_btn = page.locator("button svg, div[role='button']:has(svg), [data-testid='buttonpair-add']").first
    if await add_btn.count() == 0 or not await add_btn.is_visible():
        return False

    box = await add_btn.bounding_box()
    if box:
        await page.mouse.click(box['x'] + box['width'] / 2, box['y'] + box['height'] / 2)
    else:
        await add_btn.click(force=True)
    await page.wait_for_timeout(1200)

    # Handle variant drawer if opened
    drawer = page.locator("text='Confirm'").last
    if await drawer.count() > 0 and await drawer.is_visible():
        variant_add_btns = page.locator("text='ADD'")
        if await variant_add_btns.count() > 0:
            await variant_add_btns.last.click()
            await page.wait_for_timeout(400)
        await drawer.click()
        await page.wait_for_timeout(1000)

    # Increment quantity if > 1
    for _ in range(quantity - 1):
        plus_btn = page.locator("button:has-text('+'), div[role='button']:has-text('+')").first
        if await plus_btn.count() > 0:
            pbox = await plus_btn.bounding_box()
            if pbox:
                await page.mouse.click(pbox['x'] + pbox['width'] / 2, pbox['y'] + pbox['height'] / 2)
            else:
                await plus_btn.click(force=True)
            await page.wait_for_timeout(300)

    return True


async def select_address_if_prompted(page: Page, address_tag: str = ADDRESS_TAG):
    """
    Selects target address tag if the cart page prompts for address selection.
    """
    try:
        sel_btn = page.locator("text='Select Address'").first
        if await sel_btn.count() > 0 and await sel_btn.is_visible():
            await sel_btn.click()
            await page.wait_for_timeout(1200)
            addr_opt = page.locator(f"div:has-text('{address_tag}')").last
            if await addr_opt.count() > 0:
                await addr_opt.click()
                await page.wait_for_timeout(1500)
    except Exception:
        pass


async def inspect_cart(page: Page) -> Dict[str, Any]:
    """
    Inspects the cart page, parses items, item total, delivery fees,
    and checks if the free delivery threshold is satisfied.
    """
    if "/cart" not in page.url:
        await page.goto("https://www.swiggy.com/instamart/cart", wait_until="domcontentloaded", timeout=30000)
        await page.wait_for_timeout(1500)

    await select_address_if_prompted(page, ADDRESS_TAG)

    text = await page.evaluate("() => document.body.innerText")
    lines = [l.strip() for l in text.split('\n') if l.strip()]

    bill = {}
    missing_for_free_delivery = None
    is_store_closed = "currently closed" in text.lower()
    free_delivery_unlocked = "free delivery" in text.lower()

    # Detect deficit for free delivery
    match = re.search(r"Add items worth ₹?(\d+) to avail.*Free Delivery", text, re.I)
    if not match:
        match = re.search(r"Add ₹?(\d+) more to.*free delivery", text, re.I)
    if match:
        missing_for_free_delivery = int(match.group(1))

    # Parse standard bill elements
    try:
        idx = lines.index("BILL DETAILS")
        bill_lines = lines[idx:idx + 35]
        for i, line in enumerate(bill_lines):
            if "Item Total" in line and i + 1 < len(bill_lines):
                bill["Item Total"] = bill_lines[i + 1] if not bill_lines[i + 1].startswith("₹") else (bill_lines[i + 2] if i + 2 < len(bill_lines) and bill_lines[i + 2].startswith("₹") else bill_lines[i + 1])
            elif "Delivery Partner Fee" in line and i + 1 < len(bill_lines):
                bill["Delivery Partner Fee"] = bill_lines[i + 1]
            elif "Handling Fee" in line and i + 1 < len(bill_lines):
                bill["Handling Fee"] = bill_lines[i + 2] if i + 2 < len(bill_lines) and bill_lines[i + 2].startswith("₹") else bill_lines[i + 1]
            elif "Late Night Fee" in line and i + 1 < len(bill_lines):
                bill["Late Night Fee"] = bill_lines[i + 2] if i + 2 < len(bill_lines) and bill_lines[i + 2].startswith("₹") else bill_lines[i + 1]
            elif "To Pay" in line and i + 1 < len(bill_lines):
                bill["To Pay"] = bill_lines[i + 2] if i + 2 < len(bill_lines) and bill_lines[i + 2].startswith("₹") else bill_lines[i + 1]
    except ValueError:
        pass

    return {
        "bill": bill,
        "missing_for_free_delivery": missing_for_free_delivery,
        "is_store_closed": is_store_closed,
        "free_delivery_unlocked": free_delivery_unlocked,
        "url": page.url
    }


async def complete_checkout(page: Page, method: str = DEFAULT_PAYMENT_MODE, upi_id: Optional[str] = None) -> Dict[str, Any]:
    """
    Executes the checkout workflow based on the chosen payment method (COD, UPI, Wallet).
    """
    if "/cart" not in page.url and "/payment" not in page.url:
        await page.goto("https://www.swiggy.com/instamart/cart", wait_until="domcontentloaded", timeout=30000)
        await page.wait_for_timeout(1500)

    text = await page.evaluate("() => document.body.innerText")
    if "currently closed" in text.lower():
        return {"status": "error", "message": "Instamart store is currently closed."}

    # Proceed to Pay if on cart page
    if "/payment" not in page.url:
        pay_btn = page.locator("button:has-text('Proceed to Pay'), div[role='button']:has-text('Proceed to Pay')").first
        if await pay_btn.count() == 0 or not await pay_btn.is_visible():
            return {"status": "error", "message": "Proceed to Pay button is not active or user is not logged in."}
        await pay_btn.click()
        await page.wait_for_timeout(2500)

    method_clean = method.strip().lower()

    if method_clean in ["cod", "cash", "pod"]:
        cod_opt = page.locator("text='Pay on Delivery'").first
        if await cod_opt.count() > 0:
            await cod_opt.click()
            await page.wait_for_timeout(1000)
            confirm_btn = page.locator("button:has-text('Cash/Pay on Delivery')").first
            if await confirm_btn.count() > 0:
                await confirm_btn.click()
                return {"status": "success", "method": "cod", "message": "Order successfully submitted via Pay on Delivery!"}
        return {"status": "info", "method": "cod", "message": "Pay on Delivery selected on checkout."}

    elif method_clean in ["upi"]:
        target_upi = upi_id or DEFAULT_UPI_ID
        upi_opt = page.locator("text='Add New UPI ID', text='Enter UPI ID', text='UPI'").first
        if await upi_opt.count() > 0:
            await upi_opt.click()
            await page.wait_for_timeout(1000)

        upi_input = page.locator("input[placeholder*='UPI' i], input[placeholder*='vpa' i], input[type='text']").first
        if await upi_input.count() > 0 and target_upi:
            await upi_input.fill(target_upi)
            await page.wait_for_timeout(500)
            verify_btn = page.locator("button:has-text('Verify & Pay'), button:has-text('Proceed'), button:has-text('Request')").first
            if await verify_btn.count() > 0:
                await verify_btn.click()
                return {"status": "success", "method": "upi", "message": f"UPI collect request triggered to {target_upi}."}

        return {"status": "info", "method": "upi", "message": "UPI gateway options open on screen."}

    elif method_clean in ["wallet", "wallets"]:
        wallet_opt = page.locator("text='Wallets'").first
        if await wallet_opt.count() > 0:
            await wallet_opt.click()
            return {"status": "success", "method": "wallet", "message": "Wallet payment options displayed."}

    return {"status": "error", "message": f"Unsupported or unrecognized payment method: {method}"}
