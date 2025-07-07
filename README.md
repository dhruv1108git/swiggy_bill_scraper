# Swiggy Order Scraper

A Python script that automatically scrapes Swiggy orders delivered to a specific location (e.g., "Work"), uploads screenshots to Google Drive, and creates a Google Sheet with order details.

## Features

- 🔍 Automatically detects orders delivered to specified location
- 📸 Takes screenshots of order details
- ☁️ Uploads screenshots to Google Drive
- 📊 Creates/updates Google Sheet with order data

## Prerequisites

- Python 3.7+
- Brave Browser installed
- Google Cloud Service Account with Drive and Sheets API access
- Swiggy account with order history

## Installation

1. **Clone or download the project files**

2. **Install required Python packages:**
   ```bash
   pip install playwright pandas google-api-python-client google-auth google-auth-oauthlib google-auth-httplib2 gspread oauth2client python-dotenv
   ```

3. **Install Playwright browsers:**
   ```bash
   playwright install chromium
   ```

## Configuration

### 1. Environment Variables

Create a `.env` file in the project directory with the following variables:

```env
# Brave Browser Configuration
BRAVE_USER_DATA_DIR=~/Library/Application Support/BraveSoftware/Brave-Browser/Default
BRAVE_EXECUTABLE_PATH=/Applications/Brave Browser.app/Contents/MacOS/Brave Browser

# Google Drive Configuration
GOOGLE_DRIVE_FOLDER_ID=your_google_drive_folder_id
SERVICE_ACCOUNT_FILE=./dhruv.json

# Local Storage Configuration
BILLS_DIRECTORY=./bills

# Google Sheets Configuration
GOOGLE_SHEET_NAME=Swiggy Work Orders
WORKSHEET_NAME=Orders

# Swiggy Configuration
SWIGGY_URL=https://www.swiggy.com/
ORDERS_URL_PATTERN=**/my-account/orders
DELIVERY_LOCATION=work
```

### 2. Google Service Account Setup

1. **Create a Google Cloud Project:**
   - Go to [Google Cloud Console](https://console.cloud.google.com/)
   - Create a new project or select existing one

2. **Enable APIs:**
   - Enable Google Drive API
   - Enable Google Sheets API

3. **Create Service Account:**
   - Go to IAM & Admin → Service Accounts
   - Create a new service account
   - Download the JSON credentials file
   - Rename it to `dhruv.json` and place in project directory

4. **Share Google Drive Folder:**
   - Create a folder in Google Drive
   - Copy the folder ID from the URL (e.g., `1L6i62-BJxvSM_cu38ggzQGIJRLj9nCGK`)
   - Share the folder with your service account email (found in the JSON file)
   - Give "Editor" permissions

### 3. Brave Browser Setup

- Ensure Brave Browser is installed at the default location
- Close Brave completely before running the script
- The script will use your existing Brave profile for Swiggy login

## Usage

1. **Prepare the environment:**
   ```bash
   # Make sure Brave Browser is completely closed
   # Ensure your .env file is properly configured
   ```

2. **Run the script:**
   ```bash
   python swiggy_scraper.py
   ```

3. **Follow the prompts:**
   - The script will open Brave Browser
   - Log in to your Swiggy account
   - Navigate to your Orders page
   - The script will automatically continue

## Output

The script creates:
- **Screenshots:** Saved locally in `./bills/` directory
- **Google Drive:** Public links to uploaded screenshots
- **Google Sheet:** Contains columns:
  - `order_id`: Order number
  - `date`: Delivery date
  - `drive_link`: Google Drive public link
  - `amount`: Order amount