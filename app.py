"""
Swiggy Instamart AI Assistant - Streamlit Dashboard
Interactive UI for automated grocery ordering via Chrome DevTools Protocol (CDP).
"""

import os
import sys
import asyncio
import re
from typing import List, Tuple
import streamlit as st
from dotenv import load_dotenv

try:
    import nest_asyncio  # type: ignore
    nest_asyncio.apply()
except Exception:
    pass

# Load local environment variables
load_dotenv()

# Import backend automation functions
import backend

# Page configuration
st.set_page_config(
    page_title="Instamart Automation Assistant",
    page_icon="⚡",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom Styling
st.markdown("""
<style>
    .main-header {
        font-size: 2.2rem;
        font-weight: 700;
        color: #FC8019;
        margin-bottom: 0.2rem;
    }
    .sub-header {
        font-size: 1rem;
        color: #6c757d;
        margin-bottom: 1.5rem;
    }
    .metric-card {
        background-color: #f8f9fa;
        border-radius: 10px;
        padding: 16px;
        border: 1px solid #e9ecef;
        box-shadow: 0 2px 4px rgba(0,0,0,0.02);
    }
    .stButton>button {
        border-radius: 8px;
        font-weight: 600;
    }
</style>
""", unsafe_allow_html=True)


def run_async(coroutine):
    """Safely runs an async coroutine within Streamlit's event loop environment."""
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
                return pool.submit(asyncio.run, coroutine).result()
        return loop.run_until_complete(coroutine)
    except RuntimeError:
        return asyncio.run(coroutine)


async def check_cdp_status(cdp_url: str):
    """Validates connectivity to Chrome remote debugging."""
    from playwright.async_api import async_playwright
    try:
        async with async_playwright() as p:
            browser = await p.chromium.connect_over_cdp(cdp_url, timeout=3000)
            context = browser.contexts[0] if browser.contexts else None
            pages_count = len(context.pages) if context else 0
            swiggy_open = any("swiggy.com" in pg.url for pg in context.pages) if context else False
            await browser.close()
            return True, pages_count, swiggy_open
    except Exception as e:
        return False, 0, False


async def async_add_items(items: List[Tuple[str, int]]):
    """Adds a list of items to the Instamart cart."""
    from playwright.async_api import async_playwright
    results = []
    async with async_playwright() as p:
        browser, page = await backend.get_swiggy_page(p)
        for name, qty in items:
            success = await backend.add_item_to_cart(page, name, qty)
            results.append((name, qty, success))
        cart_info = await backend.inspect_cart(page)
    return results, cart_info


async def async_inspect_cart():
    """Inspects and returns current cart details."""
    from playwright.async_api import async_playwright
    async with async_playwright() as p:
        browser, page = await backend.get_swiggy_page(p)
        cart_info = await backend.inspect_cart(page)
    return cart_info


async def async_checkout(method: str, upi_id: str):
    """Executes order checkout with chosen payment mode."""
    from playwright.async_api import async_playwright
    async with async_playwright() as p:
        browser, page = await backend.get_swiggy_page(p)
        res = await backend.complete_checkout(page, method=method, upi_id=upi_id)
    return res


def parse_natural_command(command: str) -> List[Tuple[str, int]]:
    """
    Parses comma, plus, or 'and' separated user grocery prompts.
    e.g. '2 thums up cans, 1 munch, and 3 lays' -> [('thums up cans', 2), ('munch', 1), ('lays', 3)]
    """
    cleaned = command.replace("order", "").replace("add", "").replace("buy", "").strip()
    segments = re.split(r",|\band\b|\+", cleaned, flags=re.IGNORECASE)
    items = []
    for seg in segments:
        text = seg.strip()
        if not text:
            continue
        match = re.match(r"^(\d+)\s+(.*)$", text)
        if match:
            qty = int(match.group(1))
            name = match.group(2).strip()
        else:
            match_trailing = re.match(r"^(.*?)\s+(\d+)$", text)
            if match_trailing:
                name = match_trailing.group(1).strip()
                qty = int(match_trailing.group(2))
            else:
                name = text
                qty = 1
        if name:
            items.append((name, qty))
    return items


# ==========================================
# SIDEBAR CONFIGURATION
# ==========================================
with st.sidebar:
    st.image("https://upload.wikimedia.org/wikipedia/en/thumb/1/12/Swiggy_logo.svg/300px-Swiggy_logo.svg.png", width=140)
    st.header("⚙️ Settings & Connection")
    
    cdp_url = st.text_input(
        "Chrome Debugging URL",
        value=os.getenv("CHROME_CDP_URL", "http://localhost:9222"),
        help="Chrome remote debugging port (launched with --remote-debugging-port=9222)"
    )
    backend.CHROME_CDP_URL = cdp_url
    
    threshold = st.number_input(
        "Free Delivery Threshold (₹)",
        min_value=0,
        value=int(os.getenv("FREE_DELIVERY_THRESHOLD", 99)),
        step=10
    )
    backend.FREE_DELIVERY_THRESHOLD = threshold
    
    default_payment = st.selectbox(
        "Default Payment Mode",
        options=["cod", "upi", "wallet"],
        index=["cod", "upi", "wallet"].index(os.getenv("DEFAULT_PAYMENT_MODE", "cod").lower()) if os.getenv("DEFAULT_PAYMENT_MODE", "cod").lower() in ["cod", "upi", "wallet"] else 0
    )
    
    configured_upi = st.text_input(
        "Default UPI ID",
        value=os.getenv("UPI_ID", ""),
        placeholder="username@bank",
        help="Target VPA for UPI payment collect requests"
    )
    backend.DEFAULT_UPI_ID = configured_upi
    
    addr_tag = st.text_input(
        "Address Tag",
        value=os.getenv("ADDRESS_TAG", "WORK"),
        help="Tag name of preferred delivery address (e.g. WORK, HOME)"
    )
    backend.ADDRESS_TAG = addr_tag

    st.markdown("---")
    if st.button("🔌 Test Chrome CDP Connection", use_container_width=True):
        with st.spinner("Connecting to Chrome session..."):
            online, page_count, swiggy_open = run_async(check_cdp_status(cdp_url))
            if online:
                st.success(f"Connected! {page_count} open tabs detected.")
                if swiggy_open:
                    st.info("Swiggy Instamart tab is active.")
                else:
                    st.warning("Swiggy tab not detected yet. Assistant will open it automatically.")
            else:
                st.error("Could not reach Chrome CDP. Ensure Chrome was launched with `--remote-debugging-port=9222`.")


# ==========================================
# MAIN INTERFACE
# ==========================================
st.markdown("<div class='main-header'>⚡ Swiggy Instamart Assistant</div>", unsafe_allow_html=True)
st.markdown("<div class='sub-header'>Autonomous grocery automation with live CDP cart inspection and single-click checkout.</div>", unsafe_allow_html=True)

# Initialize Session State
if "cart_state" not in st.session_state:
    st.session_state["cart_state"] = None
if "action_history" not in st.session_state:
    st.session_state["action_history"] = []

tab_order, tab_cart, tab_checkout = st.tabs(["🛒 Quick Order & Prompt", "📋 Cart Inspection", "💳 Checkout & Pay"])

# TAB 1: ORDER
with tab_order:
    st.subheader("Add Groceries via Natural Command or Manual Input")
    
    command_input = st.text_input(
        "Voice/Text Command",
        placeholder="e.g. 2 Thums Up cans, 1 Munch, and 1 Britannia Bread",
        help="Type or dictate multiple items with quantities separated by commas or 'and'."
    )
    
    col_cmd1, col_cmd2 = st.columns([3, 1])
    with col_cmd1:
        if st.button("⚡ Process & Add Command Items", type="primary", use_container_width=True):
            if command_input.strip():
                parsed = parse_natural_command(command_input)
                if parsed:
                    st.write("Parsed Items:", parsed)
                    with st.spinner("Adding items to Instamart cart..."):
                        results, cart = run_async(async_add_items(parsed))
                        st.session_state["cart_state"] = cart
                        for name, qty, ok in results:
                            if ok:
                                st.success(f"Added {qty}x **{name}** to cart.")
                            else:
                                st.error(f"Could not find or add **{name}**.")
                else:
                    st.warning("Could not parse items from your input. Try '2 milk, 1 bread'.")
            else:
                st.info("Please enter a command first.")

    with col_cmd2:
        if st.button("🔄 Refresh Cart", use_container_width=True):
            with st.spinner("Fetching active cart details..."):
                cart = run_async(async_inspect_cart())
                st.session_state["cart_state"] = cart
                st.success("Cart synced!")

    st.markdown("---")
    st.write("##### Quick Snack Suggestions (Add ₹10 - ₹30 items to meet Free Delivery)")
    cols = st.columns(4)
    quick_items = [
        ("Nestle Munch", 1),
        ("Cadbury Dairy Milk", 1),
        ("Thums Up Can", 1),
        ("Bingo Mad Angles", 1)
    ]
    for i, (item_name, q) in enumerate(quick_items):
        with cols[i]:
            if st.button(f"+ Add {item_name}", key=f"quick_{i}", use_container_width=True):
                with st.spinner(f"Adding {item_name}..."):
                    results, cart = run_async(async_add_items([(item_name, q)]))
                    st.session_state["cart_state"] = cart
                    st.success(f"Added {item_name}!")


# TAB 2: CART INSPECTION
with tab_cart:
    st.subheader("Live Cart Summary & Free Delivery Status")
    
    cart = st.session_state.get("cart_state")
    if not cart:
        st.info("Cart has not been inspected yet. Click below to inspect active Chrome cart.")
        if st.button("🔍 Inspect Current Cart", use_container_width=True):
            with st.spinner("Inspecting cart via CDP..."):
                cart = run_async(async_inspect_cart())
                st.session_state["cart_state"] = cart
                st.rerun()
    else:
        # Check alerts
        if cart.get("is_store_closed"):
            st.error("⛔ Instamart store is currently closed at your selected address.")
        
        missing = cart.get("missing_for_free_delivery")
        if missing and missing > 0:
            st.warning(f"⚠️ Free Delivery Threshold: Add items worth **₹{missing}** to unlock Free Delivery!")
        elif cart.get("free_delivery_unlocked"):
            st.success("🎉 Free Delivery Unlocked!")

        # Bill details
        bill = cart.get("bill", {})
        if bill:
            st.markdown("#### 🧾 Bill Breakdown")
            m_cols = st.columns(len(bill)) if bill else []
            for idx, (k, v) in enumerate(bill.items()):
                with m_cols[idx]:
                    st.metric(label=k, value=v)
        else:
            st.info("No detailed bill found. Make sure items are present in your Instamart cart.")


# TAB 3: CHECKOUT
with tab_checkout:
    st.subheader("Select Payment Mode & Confirm Order")
    
    pay_mode = st.radio(
        "Payment Method",
        options=["Pay on Delivery (COD)", "UPI Collect Request", "Wallets"],
        horizontal=True
    )
    
    selected_method = "cod"
    upi_to_use = configured_upi
    
    if pay_mode == "Pay on Delivery (COD)":
        selected_method = "cod"
        st.info("Cash / Pay on Delivery will be selected on the checkout screen.")
    elif pay_mode == "UPI Collect Request":
        selected_method = "upi"
        upi_to_use = st.text_input("UPI ID / VPA for Collect Request", value=configured_upi, placeholder="username@bank")
        st.info(f"A collect request will be sent to `{upi_to_use or 'configured VPA'}`.")
    else:
        selected_method = "wallet"
        st.info("Wallets option will be selected.")

    st.markdown("---")
    confirm_col1, confirm_col2 = st.columns([2, 1])
    with confirm_col1:
        if st.button("🚀 Proceed to Pay & Place Order", type="primary", use_container_width=True):
            with st.spinner("Executing checkout workflow..."):
                res = run_async(async_checkout(selected_method, upi_to_use))
                status = res.get("status")
                msg = res.get("message", "")
                if status == "success":
                    st.success(f"✅ {msg}")
                elif status == "info":
                    st.info(f"ℹ️ {msg}")
                else:
                    st.error(f"❌ {msg}")
