# Google Drive Document Uploader

Upload large .docx files to Google Drive and automatically convert them to Google Docs format. This bypasses the 50MB web upload limit and handles files up to 500MB+ with images and formatting preserved.

## 📋 Overview

This tool solves the problem of uploading large Word documents (300+ pages, hundreds of images) to Google Drive for team collaboration. The web interface blocks large .docx files, but converting to Google Docs format removes the size restriction.

**Key Features:**
- ✓ Handles files 500MB+ (tested with 463MB dive reports)
- ✓ Preserves all images and formatting
- ✓ Progress tracking for long uploads
- ✓ Resumable uploads (recovers from interruptions)
- ✓ Upload to specific Drive folders
- ✓ Update existing documents
- ✓ Share documents with team members

---

## 🚀 Quick Start

### Prerequisites

1. **Python 3.7+** installed
2. **Required packages** (already installed if you ran the main project):
   ```bash
   pip install google-api-python-client google-auth-httplib2 google-auth-oauthlib
   ```
3. **Google Cloud Project access** (see detailed setup below)

### Basic Usage

1. **Get credentials** (one-time setup - see detailed instructions below)
2. **Place `credentials.json`** in this directory
3. **Run the script:**
   ```bash
   python upload_to_gdrive.py
   ```
4. **Follow the prompts:**
   - Browser will open for authentication (first time only)
   - Sign in with your work Google account
   - Grant permissions
   - Enter path to your .docx file
   - Optionally specify target folder

---

## 🔐 Detailed Setup Instructions

### Step 1: Get Access to Google Cloud Console

You need access to create a project in Google Cloud Console. There are two approaches:

#### Option A: Request Organizational Access (Recommended)

**Contact your IT department** and request the following:

> "I need to create a Google Cloud project to programmatically upload large files (500MB+) to Google Drive using the Drive API. Our dive report documents exceed the web interface limits and need API access.
> 
> **Required permissions:**
> - Access to Google Cloud Console (console.cloud.google.com)
> - Ability to create projects or use an existing project
> - Permission to enable APIs (Google Drive API)
> - Ability to create OAuth 2.0 credentials (Desktop application type)
> 
> **Purpose:** Upload large Word documents to our team's Google Drive for collaboration."

**What IT might provide:**
1. Direct access to create projects
2. A pre-configured project with credentials
3. A service account (alternative authentication method)

#### Option B: Use Personal Gmail (Workaround)

If organizational access is denied, you can use a personal Gmail account to create the project, then authenticate with your work account when running the script:

1. Use personal Gmail to create the project (Steps 2-7 below)
2. Download credentials to your work computer
3. When the script runs and opens a browser, **sign in with your work account**
4. Files will upload to your work Drive with your work permissions

**Note:** The credentials just provide the "authentication key" - your login determines where files go.

---

### Step 2: Access Google Cloud Console

1. Go to **https://console.cloud.google.com/**
2. Sign in with your account (work or personal per Step 1)
3. Accept Terms of Service if prompted

---

### Step 3: Create a New Project

1. **Click on the project dropdown** at the top of the page
   - Says "Select a project" or shows current project name
   - Located near the top-left, next to "Google Cloud"

2. **Click "New Project"** (top-right of popup)

3. **Configure the project:**
   - **Project name:** `Dive Report Uploader` (or any name)
   - **Organization:** Select your organization if available (or "No organization")
   - **Location:** Leave as default or select your organization

4. **Click "Create"**

5. **Wait for project creation** (10-30 seconds)
   - You'll see a notification when ready

6. **Select your new project** from the dropdown

---

### Step 4: Enable the Google Drive API

1. **Open the API Library:**
   - Click the hamburger menu (☰) in top-left
   - Navigate to: **"APIs & Services"** → **"Library"**
   - Or go directly to: https://console.cloud.google.com/apis/library

2. **Search for the API:**
   - In the search box, type: `Google Drive API`
   - Click on **"Google Drive API"** in the results

3. **Enable the API:**
   - Click the blue **"Enable"** button
   - Wait 5-10 seconds for activation
   - You'll see "API enabled" confirmation

---

### Step 5: Configure OAuth Consent Screen

Before creating credentials, you may need to configure the OAuth consent screen:

1. **Navigate to OAuth consent screen:**
   - Click hamburger menu (☰)
   - Go to: **"APIs & Services"** → **"OAuth consent screen"**

2. **Select User Type:**
   - **Internal** (if using Google Workspace - recommended)
     - Only users in your organization can use the app
   - **External** (if using personal Gmail or need wider access)
     - Any Google account can use the app
   - Click **"Create"**

3. **Fill in App Information:**
   - **App name:** `Dive Report Uploader`
   - **User support email:** Your email address
   - **Developer contact information:** Your email address
   - Leave other fields as default

4. **Click "Save and Continue"**

5. **Scopes page:**
   - Click **"Add or Remove Scopes"**
   - Search for: `drive.file`
   - Check: **`.../auth/drive.file`** (Create and delete files created by this app)
   - Click **"Update"** → **"Save and Continue"**

6. **Test users (External only):**
   - If using External, add your work email as a test user
   - Click **"Add Users"** → Enter email → **"Add"**
   - Click **"Save and Continue"**

7. **Summary:**
   - Review and click **"Back to Dashboard"**

---

### Step 6: Create OAuth 2.0 Credentials

1. **Navigate to Credentials:**
   - Hamburger menu (☰) → **"APIs & Services"** → **"Credentials"**
   - Or: https://console.cloud.google.com/apis/credentials

2. **Create Credentials:**
   - Click **"+ Create Credentials"** (near top)
   - Select **"OAuth client ID"**

3. **Select Application Type:**
   - Application type: **"Desktop app"**
   - Name: `Dive Report Desktop Client` (or any name)
   - Click **"Create"**

4. **Credentials Created:**
   - You'll see a popup: "OAuth client created"
   - Shows Client ID and Client Secret
   - Click **"OK"** (you'll download the full file next)

---

### Step 7: Download Credentials File

1. **Find your credentials:**
   - You should now see your credentials listed on the Credentials page
   - Look for your "Dive Report Desktop Client" under "OAuth 2.0 Client IDs"

2. **Download the JSON file:**
   - Click the **download icon** (⬇️) on the right side of your credential
   - The file will download with a name like:
     `client_secret_123456789-abc123def456.apps.googleusercontent.com.json`

3. **Rename the file:**
   - Rename the downloaded file to exactly: **`credentials.json`**
   - Make sure it's `.json` not `.json.txt`

4. **Move to project directory:**
   - Place `credentials.json` in this folder:
     ```
     MDBC_Data_Report_Generator/Upload_To_Gdrive/credentials.json
     ```
   - Or wherever you placed `upload_to_gdrive.py`

---

### Step 8: First Run - Authentication

1. **Run the script:**
   ```bash
   python upload_to_gdrive.py
   ```

2. **Browser will open automatically:**
   - Google Sign-In page will appear
   - **IMPORTANT:** Sign in with the account where you want files stored
   - If using Option B (personal credentials), sign in with your **work account**

3. **Grant permissions:**
   - Google will show what permissions the app needs
   - Click **"Continue"** or **"Allow"**
   - You may see a warning if the app is "unverified"
     - This is normal for personal projects
     - Click **"Advanced"** → **"Go to Dive Report Uploader (unsafe)"**

4. **Success:**
   - Browser will show: "The authentication flow has completed"
   - You can close the browser tab
   - Terminal will show: "✓ Authentication successful!"
   - A `token.pickle` file is created for future use

5. **Complete upload:**
   - Enter the path to your .docx file when prompted
   - Optionally specify target folder ID
   - Watch the progress as your file uploads

---

## 📖 Usage Examples

### Basic Upload

Upload a .docx file to your Google Drive root:

```bash
python upload_to_gdrive.py
```

**Prompts:**
```
Enter path to .docx file: C:\Reports\Dive_Report_20260203.docx
Update existing document? (y/n): n
Enter name for Google Doc (press Enter for default): [press Enter]
Enter folder ID (press Enter for My Drive root): [press Enter]
```

### Upload to Specific Folder

1. **Get folder ID from Google Drive:**
   - Open Google Drive in browser
   - Navigate to the target folder
   - Look at URL: `https://drive.google.com/drive/folders/1abc123XYZ789`
   - Folder ID is: `1abc123XYZ789`

2. **Run script and specify folder:**
   ```
   Enter folder ID (press Enter for My Drive root): 1abc123XYZ789
   ```

### Update Existing Document

Replace content of an existing Google Doc:

1. **Get document URL:**
   - Open the Google Doc
   - Copy URL from address bar

2. **Run script:**
   ```
   Update existing document? (y/n): y
   Enter Google Doc URL to update: https://docs.google.com/document/d/1def456/edit
   ```

### Programmatic Usage

Use in your own Python scripts:

```python
from upload_to_gdrive import GoogleDriveUploader

# Initialize
uploader = GoogleDriveUploader()

# Authenticate (uses saved token if available)
uploader.authenticate()

# Upload and convert
url = uploader.upload_docx(
    'C:/Reports/Dive_Report_20260203.docx',
    google_doc_name='Dive Report 2026-02-03',
    folder_id='1abc123XYZ789'  # Optional
)

print(f"Document URL: {url}")

# Share with team
file_id = uploader.extract_file_id(url)
uploader.share_file(
    file_id,
    emails=['teammate1@company.com', 'teammate2@company.com']
)
```

---

## 🔧 Troubleshooting

### "credentials.json not found"

**Solution:**
1. Make sure you downloaded the OAuth credentials (not API key)
2. Rename the file to exactly `credentials.json`
3. Place it in the same directory as `upload_to_gdrive.py`
4. Check file extension is `.json` not `.json.txt`

### "Access blocked: This app's request is invalid"

**Cause:** Incorrect application type in credentials

**Solution:**
1. Go back to Google Cloud Console → Credentials
2. Delete the existing OAuth credential
3. Create new one with Application type: **"Desktop app"** (not Web app)

### "403 Forbidden" or "Insufficient Permission"

**Solutions:**
- Verify Drive API is enabled (Step 4)
- Check OAuth consent screen is configured (Step 5)
- Try deleting `token.pickle` and re-authenticating
- If using organizational account, verify you have Drive access

### "Upload failed: Request Too Large"

**Cause:** File exceeds API limits (rare for Drive API)

**Solution:**
- Verify file size is under 5TB (Drive limit)
- For extremely large files (>2GB), upload may take very long
- Try splitting report into multiple documents

### "The authentication flow has completed" but script shows error

**Cause:** Browser closed too quickly or network issue

**Solution:**
1. Delete `token.pickle` from the directory
2. Run script again
3. Complete authentication flow
4. Wait for "Authentication successful!" in terminal before closing browser

### Script hangs at "Progress: 0%"

**Cause:** Very large file, slow upload

**Solution:**
- Be patient - 500MB files can take 10-15 minutes on slower connections
- Don't close the terminal
- Check your internet connection
- Script will resume if interrupted (resumable upload)

### "Token has been expired or revoked"

**Solution:**
1. Delete `token.pickle`
2. Run script again
3. Re-authenticate in browser

---

## 🔒 Security Notes

### Credentials File (`credentials.json`)

- **DO NOT** commit to Git (already in `.gitignore`)
- Contains your OAuth client ID and secret
- Anyone with this file can create apps using your project
- Keep it secure and local

### Token File (`token.pickle`)

- **DO NOT** commit to Git (already in `.gitignore`)
- Contains your authentication token
- Anyone with this can access your Drive (limited to files created by the app)
- Delete if compromised and re-authenticate

### OAuth Scopes

This app uses minimal permissions:
- `https://www.googleapis.com/auth/drive.file`
- Can only access files it creates or that you explicitly open with it
- Cannot see or modify other files in your Drive
- Cannot access your entire Drive

### Best Practices

1. Use organizational Google Cloud project when possible
2. Don't share credentials files
3. Revoke access if credentials are compromised:
   - Go to: https://myaccount.google.com/permissions
   - Find "Dive Report Uploader"
   - Click "Remove Access"
4. Add to `.gitignore`: `credentials.json` and `token.pickle`

---

## 📁 File Structure

```
Upload_To_Gdrive/
├── upload_to_gdrive.py      # Main script
├── credentials.json          # OAuth credentials (you download this)
├── token.pickle              # Saved authentication (created on first run)
├── Code.gs                   # Apps Script alternative (browser-based)
├── index.html                # Apps Script UI
└── README.md                 # This file
```

---

## 🆘 Getting Help

### Still Having Issues?

1. **Check the error message carefully** - they usually explain the problem
2. **Verify each setup step** - a missed step is the most common issue
3. **Try deleting `token.pickle`** and re-authenticating
4. **Check Google Cloud Console** - verify API is enabled and credentials exist

### Contact IT if:

- You cannot access Google Cloud Console
- "Access blocked" errors persist after following all steps
- Your organization blocks OAuth apps
- You need a service account instead

### Alternative: Apps Script Method

If you cannot get API access working, use the browser-based Apps Script method:
- See: `Code.gs` and `index.html` in this directory
- Works for files under 50MB
- No credentials.json needed
- Limited by Apps Script quotas

---

## 📝 Additional Resources

- [Google Drive API Documentation](https://developers.google.com/drive/api/v3/about-sdk)
- [OAuth 2.0 for Desktop Apps](https://developers.google.com/identity/protocols/oauth2/native-app)
- [Google Cloud Console](https://console.cloud.google.com/)
- [Managing OAuth Tokens](https://support.google.com/accounts/answer/3466521)

---

## 💡 Tips

- **First upload takes longest** - subsequent files are faster
- **Use folder IDs** - keeps related documents organized
- **Share after upload** - easier to share Google Docs than .docx
- **Test with small file first** - verify setup works before uploading 500MB
- **Check Drive storage** - large files count against your quota
- **Name documents clearly** - easier to find later

---

## ✅ Success Checklist

Before running the script, verify:

- ☐ Python 3.7+ installed
- ☐ Required packages installed (`pip install ...`)
- ☐ Google Cloud project created
- ☐ Google Drive API enabled
- ☐ OAuth consent screen configured
- ☐ OAuth Desktop credentials created
- ☐ `credentials.json` downloaded and renamed
- ☐ `credentials.json` in same folder as script
- ☐ .docx file ready to upload

After successful first run:

- ☐ Browser authentication completed
- ☐ `token.pickle` created
- ☐ File uploaded successfully
- ☐ Can open Google Doc in browser
- ☐ Document has all images and formatting

---

**Author:** Mike Bollinger  
**Updated:** February 2026  
**Purpose:** Upload large dive report documents to Google Drive for team collaboration
