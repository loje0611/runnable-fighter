import json
import time
import argparse
import sys
import re
import urllib.request
import urllib.error
from playwright.sync_api import sync_playwright

# Configuration
# TARGET_URL is now loaded from config.json
TEST_URL = "https://runable.me/product/3182?comp=3176"
COOKIES_FILE = "cookies.json"
LOG_FILE = "availability.log"
APPLICANT_NAME = "김건우"
CONFIG_FILE = "config.json"
SLACK_WEBHOOK_URL = "" 
TARGET_URL = "https://runable.me/product/3299?comp=2955" # Default/Fallback

def load_config():
    global SLACK_WEBHOOK_URL, TARGET_URL
    try:
        with open(CONFIG_FILE, "r") as f:
            config = json.load(f)
            SLACK_WEBHOOK_URL = config.get("slack_webhook_url", "")
            if "target_url" in config and config["target_url"]:
                TARGET_URL = config["target_url"]
    except FileNotFoundError:
        print(f"Warning: {CONFIG_FILE} not found. Using defaults/mock mode.")
    except Exception as e:
        print(f"Error loading config: {e}")

# Load config immediately
load_config()

def send_slack_alert(message):
    if not SLACK_WEBHOOK_URL:
        print(f"[Slack Mock] {message}")
        print("Tip: Set SLACK_WEBHOOK_URL in monitor_runner.py to enable real alerts.")
        return
    
    payload = {
        "text": message
    }
    
    try:
        req = urllib.request.Request(
            SLACK_WEBHOOK_URL,
            data=json.dumps(payload).encode('utf-8'),
            headers={'Content-Type': 'application/json'}
        )
        with urllib.request.urlopen(req) as response:
            if response.status == 200:
                print(f"[Slack] Notification sent: {message}")
            else:
                 print(f"[Slack] Failed to send. Status: {response.status}")
    except Exception as e:
        print(f"[Slack] Error sending notification: {e}")

def load_cookies():
    try:
        with open(COOKIES_FILE, "r") as f:
            return json.load(f)
    except FileNotFoundError:
        print(f"Error: {COOKIES_FILE} not found. Please create it with valid cookies.")
        sys.exit(1)
    except json.JSONDecodeError:
        print(f"Error: Invalid JSON in {COOKIES_FILE}.")
        sys.exit(1)

def log_availability(message):
    timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
    log_entry = f"[{timestamp}] {message}"
    print(log_entry)
    with open(LOG_FILE, "a") as f:
        f.write(log_entry + "\n")

def run_monitor(is_test=False):
    url = TEST_URL if is_test else TARGET_URL
    target_category = "10Km" if is_test else "10K" # Test event uses "10Km"

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False) # Headless=False to see what's happening, maybe change to True later
        context = browser.new_context()
        
        # Load Cookies
        cookies = load_cookies()
        context.add_cookies(cookies)
        
        page = context.new_page()
        
        print(f"Navigating to {url}...")
        page.goto(url)
        page.wait_for_load_state("networkidle")

        last_heartbeat_time = 0 # Force a heartbeat on first run
        HEARTBEAT_INTERVAL = 3600 # 1 Hour

        while True:
            try:
                # Reload page to check status
                page.reload()
                page.wait_for_load_state("networkidle")
                time.sleep(2) # Brief pause

                # Check Category via Dropdown
                # The user wants to see the process of opening                # Check Any Category
                status = check_dropdown_availability(page, "ANY")

                if "AVAILABLE" in status:
                    message = f"ALERT: A Course is AVAILABLE! Status: {status}"
                    log_availability(message)
                    send_slack_alert(message)
                    # perform_registration(page, target_category) # Optional: could try to register the found one
                    # break # Stop? User might want continuous alerts? often stop is safer to avoid spam.
                    # For monitoring, let's just sleep longer or break.
                    print("Found available slot. Notification sent.")
                    time.sleep(60) # Sleep to avoid spamming if logical error
                else:
                     # Check Heartbeat
                     current_time = time.time()
                     if current_time - last_heartbeat_time >= HEARTBEAT_INTERVAL:
                         msg = f"[{time.strftime('%H:%M:%S')}] (Heartbeat) 모니터링 정상 작동 중. 현재 신청 가능한 항목 없음."
                         print(msg)
                         send_slack_alert(msg)
                         last_heartbeat_time = current_time
                     else:
                         # Just print to console, no slack
                         print(f"[{time.strftime('%H:%M:%S')}] 확인 결과: 신청 불가 (Next Heartbeat in {int(HEARTBEAT_INTERVAL - (current_time - last_heartbeat_time))}s)")

                print("Waiting 30 seconds before next check...")
                time.sleep(30) # Monitor every 30 seconds

            except Exception as e:
                print(f"Error in monitor loop: {e}")
                time.sleep(5)

        browser.close()

def check_dropdown_availability(page, target_keyword):
    try:
        # 1. Click Apply Button if we are on main page
        # We might need to refresh if we are already on the form? 
        # For simplicity, let's assume we reload page every loop or checks if form is present.
        
        # Check if form is open?
        if page.get_by_text("참가자 이름").count() == 0:
            print("Form not visible. Clicking '대회 신청 하기'...")
            apply_btn = page.get_by_role("button", name="대회 신청 하기")
            if apply_btn.count() > 0:
                apply_btn.click()
                page.wait_for_timeout(2000) # Wait for form animation
            else:
                return "BUTTON_NOT_FOUND"

        # 2. Find and Open Dropdown "종목"
        # Based on previous analysis or user instruction
        # We need to find the element that triggers the dropdown.
        # Let's try to click the input/div that is likely the dropdown.
        
        print("Attempting to open '종목' (Course) Dropdown...")
        
        # Strategy: Find label "종목" and click the sibling or checking for a "Select" box.
        # If we can't identify the exact class, we'll try clicking 
        # 1. The label itself
        # 2. Text "선택하세요" (Please select) if visible
        # 3. Using Tab navigation from Name input
        
        # Taking a screenshot before interaction
        page.screenshot(path="before_dropdown.png")
        
        # Dump HTML for analysis
        with open("form_prod_dump.html", "w", encoding="utf-8") as f:
            f.write(page.content())
        print("Dumped form HTML to form_prod_dump.html")

        # Tab approach was unreliable.
        # Based on dump: <div><strong ...>종목</strong><div ...>Dropdown</div></div>
        # We target the div immediately following the strong tag containing "종목".
        
        print("Locating '종목' label and its sibling...")
        # Locate the Label
        course_label = page.locator("strong", has_text="종목")
        
        # Locate the Dropdown Trigger (the next sibling div)
        # We use xpath to be precise about 'following-sibling'
        dropdown_trigger = course_label.locator("xpath=following-sibling::div").first
        
        if dropdown_trigger.count() > 0:
            print("Found Dropdown Trigger. Clicking...")
            dropdown_trigger.click()
            time.sleep(1.0) # Wait for animation
        else:
            print("Could not find dropdown trigger next to '종목' label. Trying fallback...")
            # Fallback: Click the label and Tab?
            course_label.click()
            page.keyboard.press("Tab")
            page.keyboard.press("Space")
            time.sleep(1.0)

        # Capture state
        page.screenshot(path="dropdown_open.png")
        print("Captured dropdown_open.png")
        
        # 3. Analyze Options
        time.sleep(1.0) # Wait for render
        
        # Dump HTML with open dropdown
        with open("opened_dropdown.html", "w", encoding="utf-8") as f:
            f.write(page.content())
        print("Dumped opened dropdown HTML to opened_dropdown.html")

        # Interactive Verification: Try to CLICK ANY Category
        # User wants alert if ANY option is selectable.
        
        target_categories = ["10K", "10Km"]
        print(f"\n[Interactive Verification] Attempting to CLICK ANY of: {target_categories}")
        
        found_available = None
        
        # We iterate through potential categories
        # Note: If we successfully click one, the dropdown likely closes, so we should return immediately.
        
        for cat in target_categories:
            potential_options = page.get_by_text(cat).all()
            for el in potential_options:
                if el.is_visible():
                    # Check if it looks like an option (heuristic: not the label itself?)
                    # Just try clicking.
                    try:
                        print(f" Attempting click on '{cat}' candidate...")
                        el.click(timeout=500) # Short timeout for efficiency
                        print(f"  -> Click SUCCESS for {cat}!")
                        found_available = cat
                        break # Break inner loop
                    except Exception as e:
                        print(f"  -> Click failed/timeout for {cat}")
            
            if found_available:
                break # Break outer loop

        if found_available:
            return f"AVAILABLE: {found_available}"
        else:
            return "ALL_SOLD_OUT_OR_UNSELECTABLE"

        return "FORM_ERROR"

    except Exception as e:
        print(f"Check failed: {e}")
        return "ERROR"

def check_category(page, category_name):
    # This function needs to determine if a category is available.
    # Approach:
    # 1. Click on the category.
    # 2. Check if "대회 신청 하기" (Apply) button is enabled or if a Sold Out toast/message appears.
    
    try:
        # Find the category element. Using text selector for robustness
        # The structure is often: <div><strong>CategoryName</strong>...</div>
        # We try to click the text itself.
        
        # First, ensure it exists
        category_locator = page.get_by_text(category_name, exact=True)
        if category_locator.count() > 0:
            # Check for visual indicators of Sold Out (Red text, or parent class)
            # Since we couldn't easily map the class, we will rely on interaction.
            
            # Click it
            category_locator.first.click(timeout=2000)
            time.sleep(0.5)
            
            # Check Apply Button State
            # Button text: "대회 신청 하기"
            apply_btn = page.get_by_role("button", name="대회 신청 하기")
            
            if apply_btn.is_visible() and apply_btn.is_enabled():
                # Double check: sometimes clicking a sold out item shows a toast or doesn't select it?
                # Or the apply button might be there but clicking it does nothing?
                # For now, assume enabled button = Available.
                return "AVAILABLE"
            else:
                return "SOLD_OUT"
        else:
            return "NOT_FOUND"

    except Exception as e:
        # print(f"Error checking {category_name}: {e}")
        return "ERROR"

def perform_registration(page, category_name):
    try:
        # 1. Click "대회 신청 하기" on Main Page
        # The user says "Click Apply button" first.
        # Previously we clicked the category card, but maybe we should just click Apply directly if that's the flow.
        # However, monitoring usually requires selecting checking availability.
        # Let's assume we are on the main page.
        
        apply_btn = page.get_by_role("button", name="대회 신청 하기")
        if apply_btn.count() > 0:
            print("Clicking '대회 신청 하기' (Apply) button...")
            apply_btn.click()
        else:
            print("Apply button not found!")
            return

        # 2. Wait for Form & Fill Name "김건우"
        print("Waiting for registration form...")
        # We know the input name is 'participantName' from previous dump
        name_input = page.locator("input[name='participantName']")
        name_input.wait_for(state="visible", timeout=10000)
        name_input.fill(APPLICANT_NAME)
        print(f"Filled Name: {APPLICANT_NAME}")
        
        time.sleep(1)

        # 3. Select Category "10Km" (Dropdown)
        # Expected: A label "종목" and a dropdown.
        # We'll try to click the placeholder or the select element.
        # React dropdowns often use divs. Let's look for text "종목" and then the clickable area close to it,
        # or just try to find the text of the default value if any, or class-based interaction.
        # Strategy: Find text "종목" -> Traverse to finding a sibling or parent that looks clickable, OR just text search "선택하세요" (Please select) if standard.
        
        # User said: "종목" dropdown box.
        # Let's try to click the input/div associated with "종목".
        # We can try clicking the label "종목" to see if it focuses the input, or finding the element nearby.
        # Safer bet: Look for "10Km" if it's already visible? No, it's a dropdown.
        
        # Plan: Look for DOM element with text "종목" and click the NEXT container.
        # Or look for the specific structure if we had the dump.
        # We'll try to find a placeholder "옵션을 선택하세요" or similar?
        
        # Let's try clicking the *Category* label first to ensure we are in the right area, 
        # then try to click the element below it.
        
        # ACTUALLY, usually in these K-forms, the dropdown trigger has a class.
        # Let's go with a robust finding strategy: 
        # Click the area where the dropdown is likely to be.
        # Since I can't see the screen, I will dump the form text again IF I fail, but let's try to find text matching the target "10Km" *after* clicking something that looks like a dropdown.
        
        # Let's try to find a "Select" or arrow icon?
        
        # Let's try to find appropriate triggers by proximity to labels.
        # Label "종목"
        category_label = page.get_by_text("종목", exact=True)
        if category_label.count() > 0:
            # Assume the dropdown trigger is the sibling or next element
            # This is risky without inspecting.
            # However, user said "Dropdown box BELOW '종목'".
            # We can try to click the element immediately following the label in the DOM.
            pass
            
        # Let's look for "Select" related text?
        # Or... Just wait. 
        # Is there any text "선택해주세요" or "Select"?
        
        # Let's try to brute force open all dropdowns?
        # Or better, use specific text search for the dropdown *options* if they are rendered in the DOM (hidden).
        # But usually they are not.
        
        # Let's try to click the "종목" label and hit Tab to focus the dropdown, then Space to open?
        # 1. Click Name input.
        # 2. Press Tab -> Focus Category Dropdown?
        # 3. Press Space -> Open?
        # 4. Press Arrow methods?
        name_input.focus()
        page.keyboard.press("Tab")
        time.sleep(0.5)
        page.keyboard.press("Space") # Try to open
        time.sleep(1.0)
        
        # Now check if "10Km" is visible
        option_10k = page.get_by_text("10Km", exact=True)
        if option_10k.is_visible():
            print("Dropdown likely opened. Clicking '10Km'...")
            option_10k.click()
        else:
            # Maybe Tab didn't work.
            # Let's try clicking the area explicitly.
            # We will use the 'analyze_form' output we didn't fully utilize.
            # The user said "Text box" then "Dropdown".
            # Let's try clicking the text "종목" parent's sibling?
            print("Tab navigation failed/uncertain. Trying direct click on '종목' area...")
            category_label.click() # Click label
            # Maybe the dropdown is inside the label?
            # Or click the element *after* the label?
            # Let's try clicking the "Select" placeholder if it exists?
            pass

        # 4. Select Time "12:00" (Dropdown)
        # Same logic.
        print("Selecting Time '12:00'...")
        # Try finding "12:00" directly if it's already there? No, it's a dropdown.
        # Use Tab again?
        page.keyboard.press("Tab") # Move from Category to Time?
        time.sleep(0.5)
        page.keyboard.press("Space")
        time.sleep(1.0)
        
        option_time = page.get_by_text("12:00", exact=True)
        if option_time.is_visible():
            print("Time Dropdown likely opened. Clicking '12:00'...")
            option_time.click()
        
        # 5. Click "신청하기" (Submit) at the bottom
        print("Clicking Final Submit Button...")
        final_submit = page.get_by_role("button", name="신청하기")
        final_submit.click()
        
        # 6. Verify "참가자정보등록" screen
        print("Waiting for '참가자정보등록' screen...")
        page.wait_for_selector("text=참가자정보등록", timeout=5000)
        print("SUCCESS: Reached '참가자정보등록' page!")
        
        # Screenshot for proof
        page.screenshot(path="success_proof.png")
        print("Saved success_proof.png")

    except Exception as e:
        print(f"Registration failed: {e}")
        page.screenshot(path="registration_error.png")

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--test", action="store_true", help="Run in test mode against product 3182")
    args = parser.parse_args()
    
    run_monitor(is_test=args.test)
