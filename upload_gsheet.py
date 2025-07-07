import pandas as pd
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import time
import math
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

def push_df_to_gsheet(df, google_sheet_name, worksheet_name, update_existing=False, sheet_urls=None):
    """
    Pushes the given DataFrame to a Google Sheet in batches of 3500 rows.

    Args:
        df (pd.DataFrame): The DataFrame to push to the Google Sheet.
        google_sheet_name (str): The name of the Google Sheet.
        worksheet_name (str): The name of the worksheet.
        update_existing (bool): If True, append to the existing worksheet. If False, delete and recreate it.
        sheet_urls (dict, optional): A dictionary to store sheet URLs. Defaults to None.
    
    Returns:
        str: The URL of the Google Sheet.
    """

    # Fill NaN values with empty strings
    df.fillna("", inplace=True)

    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive",]
    # Authenticate using the service account credentials
    service_account_file = os.getenv('GSHEET_SERVICE_ACCOUNT_FILE', './dhruv.json')
    creds = ServiceAccountCredentials.from_json_keyfile_name(service_account_file, scope)
    client = gspread.authorize(creds)
    try:
        # Try to open the Google Sheet
        sheet = client.open(google_sheet_name)
    except gspread.exceptions.SpreadsheetNotFound: # More specific exception
        # If the sheet doesn't exist, create it
        sheet = client.create(google_sheet_name)
        # Set access to anyone with the link
        sheet.share(None, perm_type='anyone', role='writer')
    
    if sheet_urls is not None and google_sheet_name not in sheet_urls:
        sheet_urls[google_sheet_name] = sheet.url
        print(f"Google Sheet Link: {sheet.url}")


    # Determine initial shape of df for add_worksheet if needed
    # This df is the one passed to the function, before any potential modifications if update_existing=True
    initial_df_rows, initial_df_cols = df.shape

    worksheet = None # Initialize worksheet variable
    start_row = 1 # Default start_row for writing data

    try:
        worksheet = sheet.worksheet(worksheet_name)
        # Worksheet exists
        if not update_existing:
            print(f"Worksheet '{worksheet_name}' exists. Deleting and recreating as update_existing is False.")
            sheet.del_worksheet(worksheet)
            print(f"Deleted existing worksheet '{worksheet_name}'. Attempting to recreate.")
            try:
                worksheet = sheet.add_worksheet(title=worksheet_name, rows=str(initial_df_rows + 10), cols=str(initial_df_cols + 1))
                print(f"Recreated worksheet '{worksheet_name}'.")
            except gspread.exceptions.APIError as e:
                if hasattr(e, 'response') and e.response.status_code == 409:
                    print("Encountered 409 conflict after delete and add. Waiting 5 seconds and retrying add_worksheet.")
                    time.sleep(5) # Wait for 5 seconds
                    worksheet = sheet.add_worksheet(title=worksheet_name, rows=str(initial_df_rows + 10), cols=str(initial_df_cols + 1))
                    print(f"Successfully recreated worksheet '{worksheet_name}' after retry.")
                else:
                    raise # Re-raise other APIErrors
            # start_row is already 1, df for writing is the original df
        else:
            # Worksheet exists and update_existing is True
            print(f"Appending to/updating existing worksheet '{worksheet_name}'.")
            existing_data = worksheet.get_all_values()
            
            if len(existing_data) > 0:
                existing_headers = existing_data[0]
                existing_rows_content = existing_data[1:] # Use a different name to avoid conflict
                
                existing_df = pd.DataFrame(existing_rows_content, columns=existing_headers)
                
                if len(existing_df) > 0 and len(df) > 0: # Check both dfs have data
                    first_col = existing_df.columns[0]
                    
                    existing_keys = set(existing_df[first_col].astype(str))
                    new_keys = set(df[first_col].astype(str))
                    keys_to_remove = existing_keys.intersection(new_keys)
                    
                    if keys_to_remove:
                        print(f"Removing {len(keys_to_remove)} duplicate rows from existing data based on the first column.")
                        existing_df = existing_df[~existing_df[first_col].astype(str).isin(keys_to_remove)]
                    
                    # Combine filtered existing data with new data
                    if len(existing_df) > 0:
                        df = pd.concat([existing_df, df], ignore_index=True)
                    # If existing_df is empty after filtering, df remains the new data
            
            # start_row is already 1
            # Clear the worksheet before uploading the (potentially combined) data
            worksheet.clear()
            print(f"Cleared worksheet '{worksheet_name}' for updating.")

    except gspread.exceptions.WorksheetNotFound:
        # Worksheet does not exist, create it
        print(f"Worksheet '{worksheet_name}' not found. Creating new worksheet.")
        worksheet = sheet.add_worksheet(title=worksheet_name, rows=str(initial_df_rows + 10), cols=str(initial_df_cols + 1))
        print(f"New worksheet '{worksheet_name}' created.")
        # start_row is already 1, df for writing is the original df

    # Prepare the data for upload (df here is the final df to be written)
    df = df.where(pd.notnull(df), None)  # Replace NaN with None for compatibility
    data_to_upload = df.values.tolist()
    columns_list = df.columns.tolist()
    
    # Include headers in the data to be uploaded
    columns_data = [columns_list] + data_to_upload
    
    # Define batch size and number of chunks
    batch_size = 3500 # This was already defined
    total_rows_to_upload = len(columns_data)
    num_chunks = math.ceil(total_rows_to_upload / batch_size)
    
    # Update the Google Sheet in chunks
    for chunk_index in range(num_chunks):
        chunk_start_offset = chunk_index * batch_size
        chunk_end_offset = min(chunk_start_offset + batch_size, total_rows_to_upload)
        
        # Prepare the current chunk of data
        current_chunk_data = columns_data[chunk_start_offset:chunk_end_offset]
        
        # Prepare batch update request
        batch_update_requests = []
        # The gspread A1 notation is 1-indexed. start_row is where data begins (typically 1 for headers).
        for i, row_data in enumerate(current_chunk_data, start=start_row + chunk_start_offset):
            for j, value in enumerate(row_data):
                batch_update_requests.append({
                    'range': gspread.utils.rowcol_to_a1(i, j + 1), # j+1 because columns are 1-indexed
                    'values': [[value]]
                })
        
        if batch_update_requests: # Ensure there's something to update
            worksheet.batch_update(batch_update_requests)
            print(f"Updated rows {start_row + chunk_start_offset} to {start_row + chunk_start_offset + len(current_chunk_data) - 1}")
    
    return sheet.url
