# Split & Merge Workflow - Setup Guide

Complete guide for generating split reports and merging them via Apps Script.

---

## Overview

This workflow splits large dive reports into individual files (one per dive), then uses Google Apps Script to upload, convert, and merge them. This bypasses the 50MB .docx upload limit and the 6-minute execution timeout.

**Process:**
1. **Python:** Generate split reports (one .docx per dive)
2. **Apps Script:** Upload all files
3. **Apps Script:** Convert each to Google Docs
4. **Apps Script:** Merge into single document with manual checkpoints

---

## Part 1: Python Setup (Generate Split Reports)

### Step 1: Update Your Report Generator

The code has been updated with split functionality. You're ready to go!

### Step 2: Generate Split Reports

1. **Run the report generator:**
   ```bash
   python main.py
   ```

2. **Load your mission log CSV** (as usual)

3. **Add data sources** and scan for dives

4. **Select dives** to include

5. **CHECK THE NEW CHECKBOX:**
   - ☑ **"Split into separate files (one per dive)"**
   - Located in the "Output" section

6. **Click "Generate Report"**

7. **Result:**
   - Multiple files created: `Report_DIVE021_1.docx`, `Report_DIVE022_2.docx`, etc.
   - Files are named with DIVE### to ensure proper order
   - First file contains the "Appendix A" header
   - Each file is under 50MB (usually 5-40MB per dive)

**Example output:**
```
C:\Reports\
  ├── Report_DIVE021_1.docx   (15 MB)
  ├── Report_DIVE022_2.docx   (28 MB)
  ├── Report_DIVE023_3.docx   (12 MB)
  └── ... (more chunks)
```

---

## Part 2: Apps Script Setup (Upload & Merge)

### Step 1: Create Apps Script Project

1. Go to **https://script.google.com/**

2. Click **"New Project"**

3. Name it: `Report Batch Merger`

### Step 2: Add Code Files

**File 1: Code.gs**

1. Replace default code with contents of `Code_Batch_Merge.gs`
2. Save (Ctrl+S)

**File 2: index_batch.html**

1. Click the **"+"** next to Files
2. Select **"HTML"**
3. Name: `index_batch`
4. Paste contents of `index_batch.html`
5. Save

### Step 3: Enable Google Drive API

1. In the Apps Script editor, click **"Services"** (+ icon on left sidebar)
2. Find **"Google Drive API"**
3. Version: **v2**
4. Identifier: `Drive` (keep default)
5. Click **"Add"**

### Step 4: Deploy as Web App

1. Click **"Deploy"** → **"New deployment"**
2. Click the gear icon ⚙️ → Select **"Web app"**
3. Settings:
   - **Description:** `Report Batch Merger v1`
   - **Execute as:** `Me`
   - **Who has access:** `Anyone with Google account` (or restrict to your org)
4. Click **"Deploy"**
5. **Copy the Web App URL** (you'll need this)
6. Click **"Authorize access"**
   - Review permissions
   - Click **"Allow"**

---

## Part 3: Using the Batch Merger

### Step 1: Open the Web App

1. Open the **Web App URL** from deployment
2. You'll see the **Batch Upload & Merge** interface

### Step 2: Upload Files

1. **(Optional) Enter Google Drive folder ID:**
   - Open Google Drive folder where you want the merged document
   - Copy folder ID from URL: `https://drive.google.com/drive/folders/FOLDER_ID_HERE`
   - Paste into "Google Drive Folder" field
   - Leave blank for My Drive root

2. **Upload your DIVE### files:**
   - Click "Choose Files" or drag & drop
   - Select ALL `Report_DIVE###_*.docx` files at once
   - Files will be sorted automatically by name
   - Click **"Upload All Files"**
   - ✅ Wait for "X files uploaded successfully"

### Step 3: Convert to Google Docs

1. Click **"Start Converting"**
2. Wait for conversion (30-120 seconds per file)
3. **If you have 10+ files:**
   - May show "Timeout approaching" warning
   - Click **"Continue Converting"** to resume
   - Repeat until all files converted
4. ✅ Wait for "All X documents converted!"

### Step 4: Merge Documents

1. Click **"Start Merge"**
2. Master document created (link appears)
3. First batch of chunks merges automatically
4. **If timeout warning appears:**
   - Click **"Continue Merge"**
   - Repeat until complete
5. ✅ Final message: "Merge complete! All X chunks merged"
6. **Click link to open merged document**

### Checkpoint System Explained

The script uses **manual checkpoints** to prevent 6-minute timeouts:

- **Upload:** Completes all files at once (under 5 minutes for <20 files)
- **Convert:** Pauses every 5 minutes, resume with "Continue Converting"
- **Merge:** Pauses every 4.5 minutes, resume with "Continue Merge"

**Progress is saved** - if you close the page, click "Check Status" when you return.

---

## Troubleshooting

### "Timeout approaching" keeps appearing

**Normal!** Large reports with many images take time. Keep clicking "Continue" buttons until complete.

### Files uploaded but conversion failed

1. Click **"Check Status"** to see current step
2. If stuck, click **"Reset Workflow"** and try again
3. Make sure files are valid .docx (not corrupted)

### Merge creates duplicate content

This means you clicked "Continue Merge" when it was already complete. The final document is correct - just ignore duplicates or reset and re-merge.

### Want to start over

Click **"Reset Workflow"** - clears all progress and deletes uploaded/converted files.

### Master document has formatting issues

- Images may resize slightly during merge
- This is an Apps Script limitation
- Overall structure and content are preserved
- For pixel-perfect output, use the Python API method instead

---

## Performance Expectations

| Files | Upload Time | Convert Time | Merge Time | Total |
|-------|-------------|--------------|------------|-------|
| 5 files | 1-2 min | 2-5 min | 5-10 min | ~15 min |
| 10 files | 2-4 min | 5-10 min | 10-20 min | ~30 min |
| 15 files | 3-6 min | 10-15 min | 15-30 min | ~45 min |
| 20+ files | 5-10 min | 15-25 min | 30-45 min | ~60-80 min |

**Note:** Times assume 20-40MB files with lots of images. Actual times vary.

---

## Comparison: Split vs. Python API

| Factor | Split + Apps Script | Python API (upload_to_gdrive.py) |
|--------|---------------------|-----------------------------------|
| **Setup** | 30 min (first time) | 30 min (credentials) |
| **Credentials** | None (browser auth) | OAuth from Cloud Console |
| **Speed** | 30-80 min (manual) | 10-15 min (automatic) |
| **Reliability** | Good (manual steps) | Excellent (single upload) |
| **Formatting** | Good (slight changes) | Excellent (native) |
| **Best For** | No Cloud Console access | Have/can get credentials |

---

## Tips

1. **Sort files before upload** - The uploader does this automatically, but double-check your Report_DIVE###_N.docx filenames

2. **Don't close the browser** during conversion/merge - Progress is saved, but it's easier to keep it open

3. **Test with 3-5 files first** - Make sure everything works before doing a 20-file batch

4. **Monitor the master document** - You can open it during merge to watch progress

5. **Keep "Continue" clicking** - Each click processes ~2-4 chunks, so expect 3-5 clicks for 15 files

---

## Next Steps

After merge completes:

1. **Open the merged document**
2. **Share with your team:**
   - Click "Share" in Google Docs
   - Add team members
   - Set permissions (viewer/commenter/editor)
3. **Generate PDF if needed:**
   - File → Download → PDF Document

---

## File Management

After successful merge:

- **Original .docx chunks:** Safe to delete from your computer
- **Uploaded .docx files:** Automatically deleted by script during conversion
- **Converted Google Docs:** Remain in Drive (you can delete after merge if desired)
- **Merged document:** Keep this - it's your final report!

---

## Support

**If conversion/merge fails repeatedly:**

1. Check file sizes (should be under 50MB each)
2. Verify files are valid .docx (open in Word to test)
3. Try uploading fewer files at once (5-10 max)
4. Consider using the Python API method instead (more reliable for large batches)

**If you can get Google Cloud Console access:**

The Python API method (`upload_to_gdrive.py`) is faster, more reliable, and preserves formatting better. See `README.md` in Upload_To_Gdrive folder.

---

**Author:** Mike Bollinger  
**Date:** February 2026  
**Purpose:** Enable large report uploads without Cloud Console credentials
