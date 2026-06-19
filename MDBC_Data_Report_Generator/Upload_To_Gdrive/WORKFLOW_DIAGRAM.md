# Split & Merge Workflow Diagram

```
┌─────────────────────────────────────────────────────────────────────┐
│                    PYTHON: REPORT GENERATOR                         │
└─────────────────────────────────────────────────────────────────────┘
                                 │
                                 │ User Action
                                 ↓
         ┌──────────────────────────────────────────────┐
         │  ☑ Split into separate files (one per dive)  │
         └──────────────────────────────────────────────┘
                                 │
                                 │ Generate
                                 ↓
    ┌────────────────────────────────────────────────────────┐
    │  OUTPUT: Multiple .docx files                          │
    │  • Report_DIVE021_1.docx (15 MB)                       │
    │  • Report_DIVE022_2.docx (28 MB)                       │
    │  • Report_DIVE023_3.docx (12 MB)                       │
    │  ... (each < 50MB)                                     │
    └────────────────────────────────────────────────────────┘
                                 │
                                 │ User uploads files
                                 ↓
┌─────────────────────────────────────────────────────────────────────┐
│                    APPS SCRIPT: WEB INTERFACE                       │
└─────────────────────────────────────────────────────────────────────┘
                                 │
                                 ↓
╔═════════════════════════════════════════════════════════════════════╗
║  STEP 1: UPLOAD (.docx files to Google Drive)                      ║
╚═════════════════════════════════════════════════════════════════════╝
                                 │
         ┌───────────────────────┴───────────────────────┐
         │  User: Drag & drop all files                  │
         │  Script: Upload to Drive as .docx             │
         │  Time: 2-5 minutes for 10-15 files            │
         └───────────────────────┬───────────────────────┘
                                 │
                                 ↓  Status: "uploaded"
                                 │
╔═════════════════════════════════════════════════════════════════════╗
║  STEP 2: CONVERT (.docx → Google Docs)                             ║
╚═════════════════════════════════════════════════════════════════════╝
                                 │
         ┌───────────────────────┴───────────────────────┐
         │  User: Click "Start Converting"               │
         │  Script: Use Drive API to convert each file   │
         │  Time: 30-120 seconds per file                │
         │                                                │
         │  Checkpoint: Every 5 minutes                  │
         │  ├─ Saves progress                            │
         │  └─ User clicks "Continue Converting"         │
         └───────────────────────┬───────────────────────┘
                                 │
                                 ↓  Status: "converted"
                                 │
    ┌────────────────────────────────────────────────────────┐
    │  RESULT: Multiple Google Docs (sorted by name)         │
    │  • DIVE021 (Google Doc)                                │
    │  • DIVE022 (Google Doc)                                │
    │  • DIVE023 (Google Doc)                                │
    └────────────────────────────────────────────────────────┘
                                 │
                                 ↓
╔═════════════════════════════════════════════════════════════════════╗
║  STEP 3: MERGE (Combine into one document)                         ║
╚═════════════════════════════════════════════════════════════════════╝
                                 │
         ┌───────────────────────┴───────────────────────┐
         │  User: Click "Start Merge"                    │
         │  Script: Create master document               │
         │  Script: Copy content from each chunk         │
         │                                                │
         │  Merge Loop (for each chunk):                 │
         │  ├─ Open source doc                           │
         │  ├─ Copy paragraphs, tables, images           │
         │  ├─ Append to master doc                      │
         │  └─ Check time (~2-5 min per chunk)           │
         │                                                │
         │  Checkpoint: Every 4.5 minutes                │
         │  ├─ Saves current position                    │
         │  ├─ User clicks "Continue Merge"              │
         │  └─ Resumes from last chunk                   │
         └───────────────────────┬───────────────────────┘
                                 │
                                 ↓  Status: "complete"
                                 │
    ┌────────────────────────────────────────────────────────┐
    │  FINAL RESULT: Single merged Google Doc               │
    │  • Contains all dives in order                         │
    │  • Appendix A header from first chunk                  │
    │  • All images, tables, formatting                      │
    │  • Ready to share with team                            │
    └────────────────────────────────────────────────────────┘
                                 │
                                 │ User shares document
                                 ↓
                            [DONE! 🎉]


═══════════════════════════════════════════════════════════════════════
                           CHECKPOINT SYSTEM
═══════════════════════════════════════════════════════════════════════

Why checkpoints?
  Google Apps Script has a 6-minute execution limit. Processing 15+ files
  with hundreds of images will exceed this limit during convert/merge.

How it works:
  1. Script tracks progress in PropertiesService (persists across runs)
  2. Before hitting 5-6 minutes, script pauses and returns to user
  3. User clicks "Continue" button
  4. Script resumes from saved position
  5. Repeats until complete

Example timeline for 15 chunks:
  Upload:     [████████████████████████████] 3 min ✓
  Convert:    [████████████] 6 min → "Continue Converting"
              [████████████████] 5 min ✓
  Merge:      [████████] 5 min → "Continue Merge"
              [████████] 5 min → "Continue Merge"
              [████████] 4 min ✓
  
  Total: ~30 minutes, 3 manual "Continue" clicks


═══════════════════════════════════════════════════════════════════════
                         FILE NAMING CONVENTION
═══════════════════════════════════════════════════════════════════════

Python generates files with DIVE### prefix for proper sorting:

  Report_DIVE021_1.docx
         └─────┘ └─┘
            │     └── Sequential number (chunk 1 of N)
            └──────── Dive number (ensures alphabetical = chronological)

Apps Script sorts files alphabetically before processing:
  - DIVE021 comes before DIVE022
  - DIVE022 comes before DIVE023
  - etc.

This ensures the merged document has dives in correct order!


═══════════════════════════════════════════════════════════════════════
                          STATE MANAGEMENT
═══════════════════════════════════════════════════════════════════════

Apps Script uses PropertiesService to save state:

{
  "step": "merging",              // Current workflow step
  "uploadedFiles": [...],         // Array of uploaded file IDs
  "convertedDocs": [...],         // Array of converted doc IDs
  "masterDocId": "abc123",        // ID of master document
  "currentMergeIndex": 5,         // Currently merging chunk #5
  "totalChunks": 15,              // Total number of chunks
  "startTime": "2026-02-05T10:30" // When workflow started
}

This allows:
  ✓ Resume after timeout
  ✓ Close browser and return later
  ✓ Check status anytime
  ✓ Reset if something goes wrong


═══════════════════════════════════════════════════════════════════════
                        TROUBLESHOOTING FLOW
═══════════════════════════════════════════════════════════════════════

Problem: Upload fails
  └─> Check: File sizes < 50MB each?
      └─> Yes: Check internet connection
      └─> No: Re-generate with more splits

Problem: Conversion fails
  └─> Check: Files are valid .docx?
      └─> Yes: Click "Continue Converting"
      └─> No: Re-generate reports

Problem: Merge creates duplicates
  └─> Cause: Clicked "Continue" after already complete
      └─> Fix: Final document is correct, ignore duplicates
      └─> Or: Reset and re-merge

Problem: "Timeout" keeps appearing
  └─> This is normal! Keep clicking "Continue"
      └─> Each click processes 2-4 more chunks
      └─> Eventually completes

Problem: Want to start over
  └─> Click "Reset Workflow"
      └─> Clears all state
      └─> Deletes uploaded files
      └─> Ready for fresh upload


═══════════════════════════════════════════════════════════════════════
```

## Key Advantages

✅ **No OAuth credentials needed** - Browser-based authentication  
✅ **Handles files > 50MB** - Split into smaller chunks  
✅ **Bypasses 6-min timeout** - Manual checkpoints  
✅ **Preserves dive order** - Smart filename sorting  
✅ **Visual progress** - Workflow indicators  
✅ **Resumable** - State saved between runs  
✅ **One merged document** - Final result in Google Docs  

## Limitations

⚠️ **Slower than Python API** - 30-80 min vs 10-15 min  
⚠️ **Manual intervention** - Need to click "Continue" buttons  
⚠️ **Slight formatting changes** - Images may resize slightly  
⚠️ **Best for occasional use** - Not ideal for daily reports  

## When to Use This vs Python API

**Use Split + Apps Script when:**
- Can't get Google Cloud Console access
- Don't want to deal with OAuth credentials
- Willing to wait 30-80 minutes
- Comfortable with manual checkpoints

**Use Python API when:**
- Can get OAuth credentials from IT
- Need fast automated uploads
- Want perfect formatting preservation
- Generate reports frequently

