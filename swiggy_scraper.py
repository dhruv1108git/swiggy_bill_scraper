import asyncio
from playwright.async_api import async_playwright
import os
import re
import pandas as pd
from googleapiclient.discovery import build
from google.oauth2.service_account import Credentials
from upload_gsheet import push_df_to_gsheet
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Google Drive setup
SCOPES = ['https://www.googleapis.com/auth/drive']
SERVICE_ACCOUNT_FILE = os.getenv('SERVICE_ACCOUNT_FILE')
DRIVE_FOLDER_ID = os.getenv('GOOGLE_DRIVE_FOLDER_ID')

# Configuration from environment variables
BRAVE_USER_DATA_DIR = os.path.expanduser(os.getenv('BRAVE_USER_DATA_DIR', '~/Library/Application Support/BraveSoftware/Brave-Browser/Default'))
BRAVE_EXECUTABLE_PATH = os.getenv('BRAVE_EXECUTABLE_PATH', '/Applications/Brave Browser.app/Contents/MacOS/Brave Browser')
BILLS_DIRECTORY = os.getenv('BILLS_DIRECTORY', './bills')
GOOGLE_SHEET_NAME = os.getenv('GOOGLE_SHEET_NAME', 'Swiggy Work Orders')
WORKSHEET_NAME = os.getenv('WORKSHEET_NAME', 'Orders')
SWIGGY_URL = os.getenv('SWIGGY_URL', 'https://www.swiggy.com/')
ORDERS_URL_PATTERN = os.getenv('ORDERS_URL_PATTERN', '**/my-account/orders')
DELIVERY_LOCATION = os.getenv('DELIVERY_LOCATION', 'work')

def upload_to_drive(file_path, file_name):
    """Upload file to Google Drive and return the public link"""
    try:
        credentials = Credentials.from_service_account_file(SERVICE_ACCOUNT_FILE, scopes=SCOPES)
        service = build('drive', 'v3', credentials=credentials)
        
        file_metadata = {
            'name': file_name,
            'parents': [DRIVE_FOLDER_ID]
        }
        
        from googleapiclient.http import MediaFileUpload
        
        media = MediaFileUpload(file_path, resumable=True)
        file_result = service.files().create(
            body=file_metadata,
            media_body=media,
            fields='id'
        ).execute()
        
        file_id = file_result.get('id')
        
        # Make the file publicly accessible
        service.permissions().create(
            fileId=file_id,
            body={'role': 'reader', 'type': 'anyone'}
        ).execute()
        
        # Return the public link
        return f"https://drive.google.com/file/d/{file_id}/view?usp=sharing"
        
    except Exception as e:
        print(f"Error uploading to Google Drive: {e}")
        return None

async def main():
    # Initialize data collection list
    order_data = []
    
    # Create bills directory if it doesn't exist
    os.makedirs(BILLS_DIRECTORY, exist_ok=True)
    
    async with async_playwright() as p:
        # Using your Brave browser profile. Brave must be closed before running.
        brave_user_data_dir = BRAVE_USER_DATA_DIR
        brave_executable_path = BRAVE_EXECUTABLE_PATH

        if not os.path.exists(brave_executable_path):
            print(f"Error: Brave Browser not found at '{brave_executable_path}'.")
            return

        print("--- IMPORTANT ---")
        print("Please make sure Brave Browser is completely closed before proceeding.")
        print("-----------------")

        try:
            context = await p.chromium.launch_persistent_context(
                brave_user_data_dir,
                headless=False,
                executable_path=brave_executable_path
            )
        except Exception as e:
            if "ProcessSingleton" in str(e):
                print("\nError: Brave Browser is already running.")
                print("Please close Brave completely and run the script again.")
            else:
                print(f"\nAn error occurred launching Brave: {e}")
            return

        # I will close old tabs and start with a fresh page.
        if context.pages:
            page = context.pages[0]
            for old_page in context.pages[1:]:
                await old_page.close()
        else:
            page = await context.new_page()

        try:
            # Go to the homepage first.
            print(f"\nNavigating to the Swiggy homepage...")
            await page.goto(SWIGGY_URL, wait_until="domcontentloaded")

            print("\n--- ACTION REQUIRED ---")
            print("Please log in to your Swiggy account in the browser window.")
            print("Then, navigate to your Orders page.")
            print("The script will automatically continue once you are on the orders page.")
            print("-----------------------")
            
            # Wait for you to navigate to the orders page. Timeout=0 means it will wait forever.
            await page.wait_for_url(ORDERS_URL_PATTERN, timeout=0)
            print("\nOrders page detected! Starting the scraping process...")
            await page.wait_for_load_state("networkidle")

            # First, click "Show More Orders" until all are loaded.
            while True:
                try:
                    show_more_button = page.locator("text=Show More Orders")
                    await show_more_button.click(timeout=7000) # 7s timeout
                    print("Clicked 'Show More Orders'...")
                    await page.wait_for_load_state("networkidle")
                except Exception:
                    print("All orders seem to be loaded.")
                    break

            # Now, process each order.
            view_details_buttons = await page.locator("text=VIEW DETAILS").all()
            num_orders = len(view_details_buttons)
            print(f"Found {num_orders} orders to process.")

            for i in range(num_orders):
                # Before each click, check for and close any pop-up overlays.
                try:
                    # As you pointed out, I am now using the correct selector for the close button.
                    close_button_selector = "span[class='_1X6No icon-close']"
                    close_button = page.locator(close_button_selector).first
                    if await close_button.is_visible(timeout=1000): # Quick check if it exists
                         print("Popup detected, attempting to close it...")
                         await close_button.click()
                         await page.wait_for_timeout(500) # Wait half a second after closing
                except Exception:
                    # No overlay found, which is the normal case.
                    pass

                all_buttons = await page.locator("text=VIEW DETAILS").all()
                if i >= len(all_buttons):
                    print("Error: Could not find the next 'VIEW DETAILS' button.")
                    break
                
                button = all_buttons[i]
                print(f"\nProcessing order {i + 1} of {num_orders}...")
                
                # As requested, waiting 1 second before clicking.
                await page.wait_for_timeout(1000)
                
                await button.click()
                
                # As requested, waiting 1 second after clicking for the page to react.
                await page.wait_for_timeout(1000)
                
                print(f"Checking if order was delivered to '{DELIVERY_LOCATION}'...")
                try:
                    # I'll wait for the delivery location label to appear. If it doesn't in 5s, I'll skip.
                    await page.wait_for_selector(f"text={DELIVERY_LOCATION}", timeout=5000)
                    print(f"Order delivered to '{DELIVERY_LOCATION}'. Preparing to take screenshot.")

                    # If delivery location is found, I'll proceed with screenshot logic.
                    screenshot_path = f"swiggy_order_details_{i + 1}.png" # Default name
                    amount = None
                    order_id = None
                    
                    try:
                        # Extract amount from rupee div
                        amount_element = page.locator("div.rupee").first
                        if await amount_element.is_visible():
                            amount = await amount_element.inner_text()
                            print(f"Found amount: {amount}")
                        else:
                            print("Warning: Amount not found")
                    except Exception as e:
                        print(f"Warning: Could not extract amount ({e})")
                    
                    try:
                        # Extract order ID from _1Hjkp div
                        order_id_element = page.locator("div._1Hjkp").first
                        if await order_id_element.is_visible():
                            order_id_text = await order_id_element.inner_text()
                            # Extract just the number part from "Order #210866936984562"
                            order_id = order_id_text.replace("Order #", "").strip()
                            print(f"Found order ID: {order_id}")
                        else:
                            print("Warning: Order ID not found")
                    except Exception as e:
                        print(f"Warning: Could not extract order ID ({e})")
                    
                    try:
                        # Based on your feedback, I'll now use the specific class to get the delivery date.
                        date_container_selector = "div._2kNey:has-text('Delivered on')"
                        date_container = page.locator(date_container_selector).first
                        
                        full_text = await date_container.inner_text()
                        # The date is on the first line, per your example.
                        date_line = full_text.splitlines()[0]

                        # I'm using regex for a case-insensitive replacement of "Delivered on".
                        date_part = re.sub(r'delivered on\s*', '', date_line, flags=re.IGNORECASE).strip()
                        
                        if date_part:
                            # Sanitize for filename: remove commas, replace spaces and colons.
                            sanitized_date = date_part.replace(",", "").replace(" ", "_").replace(":", "_")
                            
                            if len(sanitized_date) > 50 or not sanitized_date.strip():
                                raise ValueError(f"Extracted date seems invalid: '{sanitized_date}'")

                            screenshot_path = os.path.join(BILLS_DIRECTORY, f"{sanitized_date[4:]}.png")
                            print(f"Found delivery date. Will save screenshot as: {screenshot_path}")
                        else:
                            raise ValueError("Could not extract date from container.")
                    except Exception as e:
                        print(f"Warning: Could not find delivery date ({e}). Using default name: {screenshot_path}")

                    await page.screenshot(path=screenshot_path)
                    print(f"Screenshot saved: {screenshot_path}")
                    
                    # Upload to Google Drive
                    print("Uploading to Google Drive...")
                    file_name = os.path.basename(screenshot_path)
                    drive_link = upload_to_drive(screenshot_path, file_name)
                    
                    if drive_link:
                        print(f"Successfully uploaded to Google Drive: {drive_link}")
                        
                        # Add data to collection
                        order_data.append({
                            'order_id': order_id if order_id else 'Unknown',
                            'date': date_part if 'date_part' in locals() and date_part else 'Unknown',
                            'drive_link': drive_link,
                            'amount': amount if amount else 'Unknown'
                        })
                    else:
                        print("Failed to upload to Google Drive")

                except Exception:
                    # This catches the timeout from wait_for_selector if delivery location isn't found.
                    print(f"Order not delivered to '{DELIVERY_LOCATION}', skipping screenshot.")

                # As you suggested, I will click the left side of the screen to go back.
                print("Returning to orders page by clicking the left side of the screen...")
                await page.mouse.click(100, 250) # Clicking coordinates to dismiss the details view.

                # I'm adding a robust wait here to ensure the order list is re-loaded.
                print("Waiting for orders page to re-load...")
                await page.wait_for_selector("text=VIEW DETAILS", timeout=30000)

        except Exception as e:
            print(f"\nAn error occurred during automation: {e}")

        finally:
            print("\nScript finished. Browser window will close.")
            
            # Create Google Sheet with collected data
            if order_data:
                print(f"\nCreating Google Sheet with {len(order_data)} orders...")
                df = pd.DataFrame(order_data)
                
                try:
                    sheet_url = push_df_to_gsheet(
                        df=df,
                        google_sheet_name=GOOGLE_SHEET_NAME,
                        worksheet_name=WORKSHEET_NAME,
                        update_existing=True
                    )
                    print(f"Google Sheet created/updated: {sheet_url}")
                except Exception as e:
                    print(f"Error creating Google Sheet: {e}")
            else:
                print(f"No {DELIVERY_LOCATION} orders found to upload to Google Sheet.")
            
            await context.close()

if __name__ == "__main__":
    asyncio.run(main()) 