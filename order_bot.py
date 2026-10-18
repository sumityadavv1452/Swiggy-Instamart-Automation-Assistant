import sys
import asyncio
import json
import re

import os
from dotenv import load_dotenv

load_dotenv()

if sys.stdout and hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
from playwright.async_api import async_playwright

CDP_URL = os.getenv("CHROME_CDP_URL", "http://localhost:9222")
UPI_ID = os.getenv("UPI_ID", "yourname@upi")

async def get_page(p):
    browser = await p.chromium.connect_over_cdp(CDP_URL)
    context = browser.contexts[0] if browser.contexts else await browser.new_context()
    swiggy_pages = [pg for pg in context.pages if "swiggy.com" in pg.url]
    page = swiggy_pages[0] if swiggy_pages else (context.pages[0] if context.pages else await context.new_page())
    return browser, page

async def add_item_to_cart(page, item_name: str, quantity: int = 1):
    search_url = f"https://www.swiggy.com/instamart/search?custom_back=true&query={item_name}"
    await page.goto(search_url, wait_until="domcontentloaded", timeout=30000)
    await page.wait_for_timeout(1500)

    # Locate add button
    add_btn = page.locator("button svg, div[role='button']:has(svg), [data-testid='buttonpair-add']").first
    if await add_btn.count() > 0 and await add_btn.is_visible():
        box = await add_btn.bounding_box()
        if box:
            await page.mouse.click(box['x'] + box['width'] / 2, box['y'] + box['height'] / 2)
        else:
            await add_btn.click(force=True)
    await page.wait_for_timeout(1200)

    # If variant drawer opens
    drawer = page.locator("text='Confirm'").last
    if await drawer.count() > 0 and await drawer.is_visible():
        add_btns = page.locator("text='ADD'")
        if await add_btns.count() > 0:
            await add_btns.last.click()
            await page.wait_for_timeout(300)
        await drawer.click()
        await page.wait_for_timeout(1000)

    # Handle extra quantities if requested
    for _ in range(quantity - 1):
        plus_btn = page.locator("button:has-text('+'), div[role='button']:has-text('+')").first
        if await plus_btn.count() > 0:
            pbox = await plus_btn.bounding_box()
            if pbox:
                await page.mouse.click(pbox['x'] + pbox['width'] / 2, pbox['y'] + pbox['height'] / 2)
            else:
                await plus_btn.click(force=True)
            await page.wait_for_timeout(300)

async def inspect_cart(page):
    if "/cart" not in page.url:
        await page.goto("https://www.swiggy.com/instamart/cart", wait_until="domcontentloaded", timeout=30000)
        await page.wait_for_timeout(1500)

    text = await page.evaluate("() => document.body.innerText")
    lines = [l.strip() for l in text.split('\n') if l.strip()]

    bill = {}
    missing_for_free_delivery = None

    match = re.search(r"Add items worth ₹?(\d+) to avail.*Free Delivery", text, re.I)
    if not match:
        match = re.search(r"Add ₹?(\d+) more to.*free delivery", text, re.I)
    if match:
        missing_for_free_delivery = int(match.group(1))

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
            elif "To Pay" in line and i + 1 < len(bill_lines):
                bill["To Pay"] = bill_lines[i + 2] if i + 2 < len(bill_lines) and bill_lines[i + 2].startswith("₹") else bill_lines[i + 1]
    except ValueError:
        pass

    return {
        "bill": bill,
        "missing_for_free_delivery": missing_for_free_delivery,
        "raw_text": text
    }

async def complete_payment(page, method: str = "upi"):
    if "/cart" not in page.url and "/payment" not in page.url:
        await page.goto("https://www.swiggy.com/instamart/cart", wait_until="domcontentloaded", timeout=30000)
        await page.wait_for_timeout(1500)

    if "/payment" not in page.url:
        text = await page.evaluate("() => document.body.innerText")
        if "currently closed" in text.lower():
            print("STORE_CLOSED: Instamart store is currently closed.", flush=True)
            return

        pay_btn = page.locator("text='Proceed to Pay'").first
        if await pay_btn.count() == 0 or not await pay_btn.is_visible():
            print("STORE_CLOSED: 'Proceed to Pay' is not enabled or store is unavailable.", flush=True)
            return

        await pay_btn.click()
        await page.wait_for_timeout(2000)

    method_clean = method.strip().lower()
    if method_clean in ["upi"]:
        upi_opt = page.locator("text='Add New UPI ID', text='Enter UPI ID', text='UPI'").first
        if await upi_opt.count() > 0:
            await upi_opt.click()
            await page.wait_for_timeout(1000)

        upi_input = page.locator("input[placeholder*='UPI' i], input[placeholder*='vpa' i], input[type='text']").first
        if await upi_input.count() > 0:
            await upi_input.fill(UPI_ID)
            await page.wait_for_timeout(500)
            verify_btn = page.locator("button:has-text('Verify & Pay'), button:has-text('Proceed'), button:has-text('Request')").first
            if await verify_btn.count() > 0:
                await verify_btn.click()
                print(f"UPI collect request sent to {UPI_ID}. Please approve on your phone.", flush=True)
                return
    elif method_clean in ["cod", "cash"]:
        cod_opt = page.locator("text='Pay on Delivery'").first
        if await cod_opt.count() > 0:
            await cod_opt.click()
            await page.wait_for_timeout(1000)
            confirm_btn = page.locator("button:has-text('Cash/Pay on Delivery')").first
            if await confirm_btn.count() > 0:
                await confirm_btn.click()
                print("Order placed via Cash on Delivery.", flush=True)
                return
    elif method_clean in ["wallet", "wallets"]:
        wallet_opt = page.locator("text='Wallets'").first
        if await wallet_opt.count() > 0:
            await wallet_opt.click()
            print("Wallet option selected.", flush=True)

async def main():
    if len(sys.argv) < 2:
        return
    cmd = sys.argv[1].lower()
    async with async_playwright() as p:
        browser, page = await get_page(p)
        if cmd == "add":
            item = sys.argv[2] if len(sys.argv) > 2 else ""
            qty = int(sys.argv[3]) if len(sys.argv) > 3 else 1
            await add_item_to_cart(page, item, qty)
            status = await inspect_cart(page)
            print("STATUS_JSON:" + json.dumps(status, ensure_ascii=False))
        elif cmd == "status":
            status = await inspect_cart(page)
            print("STATUS_JSON:" + json.dumps(status, ensure_ascii=False))
        elif cmd in ["pay", "checkout"]:
            method = sys.argv[2] if len(sys.argv) > 2 else "upi"
            await complete_payment(page, method)

if __name__ == "__main__":
    asyncio.run(main())