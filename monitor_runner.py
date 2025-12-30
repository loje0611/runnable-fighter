import json
import time
import argparse
import sys
import logging
import urllib.request
import urllib.error
from typing import List, Dict, Optional, Any
from playwright.sync_api import sync_playwright, Page

# --- Configuration & Constants ---

class Config:
    TEST_URL: str = "https://runable.me/product/3182?comp=3176"
    CONFIG_FILE: str = "config.json"
    
    # Defaults
    SLACK_WEBHOOK_URL: Optional[str] = None
    TARGET_URL: Optional[str] = None
    MONITORING_INTERVAL: int = 30
    ENABLE_HEARTBEAT: bool = True
    TARGET_CATEGORIES: List[str] = ["10K", "10Km"]
    HEADLESS: bool = False
    COOKIES_FILE: str = "cookies.json"
    LOG_FILE: str = "availability.log"

    @classmethod
    def load(cls) -> None:
        try:
            with open(cls.CONFIG_FILE, "r") as f:
                data = json.load(f)
                cls.SLACK_WEBHOOK_URL = data.get("slack_webhook_url")
                cls.TARGET_URL = data.get("target_url")
                cls.MONITORING_INTERVAL = data.get("monitoring_interval", 30)
                cls.ENABLE_HEARTBEAT = data.get("enable_heartbeat", True)
                cls.TARGET_CATEGORIES = data.get("target_categories", ["10K", "10Km"])
                cls.HEADLESS = data.get("headless", False)
                cls.COOKIES_FILE = data.get("cookies_file", "cookies.json")
                cls.LOG_FILE = data.get("log_file", "availability.log")
                
            if not cls.SLACK_WEBHOOK_URL or not cls.TARGET_URL:
                logging.error(f"slack_webhook_url or target_url is missing in {cls.CONFIG_FILE}")
                sys.exit(1)
                
        except FileNotFoundError:
            logging.error(f"{cls.CONFIG_FILE} not found. Please copy config.sample.json to {cls.CONFIG_FILE} and edit it.")
            sys.exit(1)
        except Exception as e:
            logging.error(f"Error loading config: {e}")
            sys.exit(1)

# --- Logging Setup ---

def setup_logging(log_file: str) -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="[%(asctime)s] %(levelname)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
        handlers=[
            logging.FileHandler(log_file, encoding='utf-8'),
            logging.StreamHandler(sys.stdout)
        ]
    )

# --- Helper Functions ---

def send_slack_alert(message: str) -> None:
    if not Config.SLACK_WEBHOOK_URL:
        logging.info(f"[Slack Mock] {message}")
        logging.info("Tip: Set SLACK_WEBHOOK_URL in config.json to enable real alerts.")
        return
    
    payload = {"text": message}
    
    try:
        req = urllib.request.Request(
            Config.SLACK_WEBHOOK_URL,
            data=json.dumps(payload).encode('utf-8'),
            headers={'Content-Type': 'application/json'}
        )
        with urllib.request.urlopen(req) as response:
            if response.status == 200:
                logging.info(f"[Slack] Notification sent: {message}")
            else:
                 logging.error(f"[Slack] Failed to send. Status: {response.status}")
    except Exception as e:
        logging.error(f"[Slack] Error sending notification: {e}")

def load_cookies(cookies_path: str) -> List[Dict[str, Any]]:
    try:
        with open(cookies_path, "r") as f:
            return json.load(f)
    except FileNotFoundError:
        logging.error(f"{cookies_path} not found. Please create it with valid cookies.")
        sys.exit(1)
    except json.JSONDecodeError:
        logging.error(f"Invalid JSON in {cookies_path}.")
        sys.exit(1)

def check_dropdown_availability(page: Page, target_categories_list: List[str]) -> str:
    try:
        # 1. Click Apply Button if form is not visible
        if page.get_by_text("참가자 이름").count() == 0:
            logging.info("Form not visible. Clicking '대회 신청 하기'...")
            apply_btn = page.get_by_role("button", name="대회 신청 하기")
            if apply_btn.count() > 0:
                apply_btn.click()
                page.wait_for_timeout(2000) # Wait for form animation
            else:
                return "BUTTON_NOT_FOUND"

        # 2. Find and Open Dropdown "종목"
        logging.info("Attempting to open '종목' (Course) Dropdown...")
        
        # Locate the Label "종목"
        course_label = page.locator("strong", has_text="종목")
        
        # Locate the Dropdown Trigger (the next sibling div)
        dropdown_trigger = course_label.locator("xpath=following-sibling::div").first
        
        if dropdown_trigger.count() > 0:
            dropdown_trigger.click()
            time.sleep(1.0) # Wait for animation
        else:
            logging.warning("Could not find dropdown trigger next to '종목' label. Trying fallback...")
            # Fallback: Click the label and Tab/Space
            course_label.click()
            page.keyboard.press("Tab")
            page.keyboard.press("Space")
            time.sleep(1.0)

        # 3. Interactive Verification: Try to CLICK ANY Category
        logging.info(f"[Check] Verifying availability for: {target_categories_list}")
        
        found_available = None
        
        for cat in target_categories_list:
            potential_options = page.get_by_text(cat).all()
            for el in potential_options:
                if el.is_visible():
                    try:
                        # logging.debug(f" Attempting click on '{cat}' candidate...")
                        el.click(timeout=500)
                        logging.info(f"  -> Click SUCCESS for {cat}!")
                        found_available = cat
                        break 
                    except Exception:
                        pass
            
            if found_available:
                break 

        if found_available:
            return f"AVAILABLE: {found_available}"
        else:
            return "ALL_SOLD_OUT_OR_UNSELECTABLE"

    except Exception as e:
        logging.error(f"Check failed: {e}")
        return "ERROR"

# --- Main Logic ---

def run_monitor(is_test: bool = False) -> None:
    # Setup Logging
    # We load config primarily to get paths, but Config.load() handles everything.
    # However, we need to setup logging *after* we know where to log, 
    # but Config.load might default to 'availability.log' if fail.
    # Let's just load config first. Errors in loading will print to stdout.
    
    # Re-loading config here inside main execution to ensure freshness or simply init.
    Config.load()
    setup_logging(Config.LOG_FILE)
    
    url = Config.TEST_URL if is_test else Config.TARGET_URL
    target_cats = Config.TARGET_CATEGORIES 
    
    if not url:
        logging.error("Target URL is not set.")
        return

    logging.info(f"Starting Monitor for {url}")
    logging.info(f"Target Categories: {target_cats}")
    logging.info(f"Headless Mode: {Config.HEADLESS}")

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=Config.HEADLESS)
        context = browser.new_context()
        
        # Load Cookies
        cookies = load_cookies(Config.COOKIES_FILE)
        context.add_cookies(cookies)
        
        page = context.new_page()
        
        logging.info(f"Navigating to page...")
        try:
            page.goto(url)
            page.wait_for_load_state("networkidle")
        except Exception as e:
            logging.error(f"Failed to load page: {e}")
            return

        last_heartbeat_time = 0.0
        HEARTBEAT_INTERVAL = 3600 # 1 Hour

        while True:
            try:
                # Reload page to check status
                page.reload()
                page.wait_for_load_state("networkidle")
                time.sleep(2) 

                status = check_dropdown_availability(page, target_cats)

                if "AVAILABLE" in status:
                    message = f"ALERT: A Course is AVAILABLE! Status: {status}"
                    logging.info(message)
                    send_slack_alert(message)
                    logging.info("Found available slot. Notification sent.")
                    time.sleep(60) # Sleep to avoid spamming
                else:
                     # Check Heartbeat
                     current_time = time.time()
                     if Config.ENABLE_HEARTBEAT and (current_time - last_heartbeat_time >= HEARTBEAT_INTERVAL):
                         msg = f"(Heartbeat) 모니터링 정상 작동 중. 현재 신청 가능한 항목 없음."
                         logging.info(msg)
                         send_slack_alert(msg)
                         last_heartbeat_time = current_time
                     else:
                         logging.info(f"확인 결과: 신청 불가 (Target: {target_cats})")

                logging.info(f"Waiting {Config.MONITORING_INTERVAL} seconds before next check...")
                time.sleep(Config.MONITORING_INTERVAL)

            except KeyboardInterrupt:
                logging.info("Stopping monitor...")
                break
            except Exception as e:
                logging.error(f"Error in monitor loop: {e}")
                time.sleep(5)

        browser.close()

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--test", action="store_true", help="Run in test mode against product 3182")
    args = parser.parse_args()
    
    # Initial config load to check validity before starting
    Config.load()
    
    run_monitor(is_test=args.test)
