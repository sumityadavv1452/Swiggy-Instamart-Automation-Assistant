# ⚡ Swiggy Instamart Automation Assistant

An autonomous grocery shopping assistant and dashboard for **Swiggy Instamart**, powered by **Playwright**, **Chrome DevTools Protocol (CDP)**, and **Streamlit**.

The assistant connects directly to your authenticated local Chrome browser session, executing rapid product searches, variant handling, threshold checks for free delivery, and one-click checkouts without repetitive manual clicking.

---

## 🌟 Key Features

- **Direct Chrome Session Control (CDP)**: Seamlessly operates inside your existing, logged-in browser session—no OTP logins, re-authentication, or bot detection triggers.
- **Fast Product Search & Cart Addition**: Navigates straight to query endpoints, automatically dismissing variant selection drawers and handling multi-quantity additions.
- **Dynamic Free Delivery Threshold Alerts**: Automatically inspects bill details (Item Total, Delivery Partner Fee, Handling Fee, Late Night Fee) and calculates the exact amount needed to unlock Free Delivery.
- **Smart Additions**: Suggests quick, inexpensive snack items (e.g., Munch, Dairy Milk, Kurkure) to hit the free delivery threshold and save on delivery charges.
- **Multi-Mode Checkout Automation**:
  - **Pay on Delivery (COD)**: Selects Cash/Pay on Delivery and confirms the order.
  - **UPI Collect Request**: Dispatches a UPI collect request directly to your registered VPA for mobile approval.
  - **Wallets**: Opens wallet checkout options.
- **Interactive Streamlit UI**: User-friendly web interface with natural language command parsing, real-time bill breakdown metrics, and instant checkout buttons.
- **Lightweight CLI / MCP Tool**: Includes `order_bot.py` for integration into IDEs, agents, or automated terminal pipelines.

---

## 🏗️ Architecture

```
┌─────────────────────────────────┐       ┌─────────────────────────────────┐
│     Streamlit Dashboard         │       │          CLI / Agent            │
│          (app.py)               │       │        (order_bot.py)           │
└────────────────┬────────────────┘       └────────────────┬────────────────┘
                 │                                         │
                 └──────────────────┬──────────────────────┘
                                    │
                                    ▼
                     ┌─────────────────────────────┐
                     │     Backend Controller      │
                     │        (backend.py)         │
                     └──────────────┬──────────────┘
                                    │  CDP (ws://localhost:9222)
                                    ▼
                     ┌─────────────────────────────┐
                     │    Active Chrome Session    │
                     │  (Logged-in to Swiggy.com)  │
                     └─────────────────────────────┘
```

---

## 📋 Prerequisites

- **Python**: 3.10 or higher
- **Google Chrome**: Installed locally
- An active Swiggy Instamart account

---

## 🚀 Getting Started

### 1. Launch Chrome in Remote Debugging Mode

Ensure all existing instances of Chrome are closed, then launch Chrome with remote debugging enabled on port `9222`.

#### **Windows (Command Prompt / PowerShell)**
```cmd
chrome.exe --remote-debugging-port=9222 --user-data-dir="C:\chrome_dev_session"
```
*(If `chrome.exe` is not in your PATH, run it from `C:\Program Files\Google\Chrome\Application\chrome.exe`)*

#### **macOS**
```bash
/Applications/Google\ Chrome.app/Contents/MacOS/Google\ Chrome --remote-debugging-port=9222 --user-data-dir="/tmp/chrome_dev_session"
```

#### **Linux**
```bash
google-chrome --remote-debugging-port=9222 --user-data-dir="/tmp/chrome_dev_session"
```

> **Important**: Once Chrome opens, navigate to [swiggy.com/instamart](https://www.swiggy.com/instamart), log in with your phone number, and select your preferred delivery address tag (e.g., WORK or HOME).

---

### 2. Install Project Dependencies

Clone the repository and install the required Python packages:

```bash
git clone <your-repository-url>
cd <repository-directory>

pip install -r requirements.txt
playwright install chromium
```

---

### 3. Configure Environment Variables

Copy the example environment configuration:

```bash
cp .env.example .env
```

Edit `.env` to customize your preferences:

```ini
# Chrome Remote Debugging URL
CHROME_CDP_URL=http://localhost:9222

# Free Delivery Threshold in INR (default is 99)
FREE_DELIVERY_THRESHOLD=99

# Default payment mode: 'cod', 'upi', or 'wallet'
DEFAULT_PAYMENT_MODE=cod

# Optional UPI ID for collect requests
UPI_ID=yourname@bank

# Target address tag in Swiggy
ADDRESS_TAG=WORK
```

---

## 💻 Usage

### Option A: Streamlit Dashboard (Recommended)

Start the interactive web dashboard:

```bash
streamlit run app.py
```

Features available in the dashboard:
1. **Natural Language / Voice Command Bar**: Type or paste prompts like `"2 Thums Up cans, 1 Munch, and 1 Britannia Bread"` and click **Process & Add**.
2. **Live Cart Metrics**: View active bill details, item totals, and delivery partner fees directly from the browser session.
3. **Free Delivery Advisor**: Notifies you if your cart is under the free delivery limit and offers 1-click snack addition buttons.
4. **Checkout Trigger**: Choose between COD or UPI collect request and place your order instantly.

---

### Option B: Command Line Script

You can also run automated tasks via `order_bot.py`:

```bash
# Check current cart status and bill details
python order_bot.py status

# Add an item with quantity
python order_bot.py add "Nestle Munch" 2

# Trigger checkout
python order_bot.py checkout cod
```

---

## 🔒 Security & Privacy

- **No Stored Credentials**: This tool does not store or transmit passwords, session tokens, cookies, or OTPs. All authentication is maintained entirely within your own local Chrome browser profile.
- **Configurable Personal Data**: UPI VPAs, delivery address tags, and debug endpoints are strictly managed through local `.env` variables that are excluded from version control by `.gitignore`.

---

## 📄 License

Distributed under the MIT License. See `LICENSE` for more information.

---

## ⚠️ Disclaimer

This project is an independent automation tool developed for personal productivity and educational purposes. It is not affiliated with, maintained, or endorsed by Swiggy or Bundl Technologies Pvt. Ltd. Use responsibly and in accordance with Swiggy's Terms of Service.
