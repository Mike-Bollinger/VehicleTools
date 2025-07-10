"""
Setup Instructions for Word Document Report Generator:

This version creates Word (.docx) documents instead of Google Docs since 
your organization doesn't have Google Cloud access.

1. Install required packages: pip install -r requirements.txt
2. Make sure your Google Sheet is publicly viewable:
   - Open your Google Sheet
   - Click "Share" button
   - Change permissions to "Anyone with the link can view"
3. Update the base_path in the script if your dive folders are in a different location
4. Run: python Google_Report_Generator.py

The script will:
- Download data from your Google Sheet (no authentication needed if public)
- Find all DIVE folders with Report_Plots subdirectories
- Create a Word document with structured sections for each dive
- Include images from each dive's Report_Plots folder
- Save the document in the same directory as the script
"""

print("Setup Instructions for Word Document Report Generator:")
print()
print("This version creates Word (.docx) documents")
print()
print("1. Install packages: pip install -r requirements.txt")
print("2. Make your Google Sheet publicly viewable:")
print("   - Open your Google Sheet")
print("   - Click 'Share' button") 
print("   - Change to 'Anyone with the link can view'")
print("3. Update base_path in script if needed")
print("4. Run: python Google_Report_Generator.py")
print()
