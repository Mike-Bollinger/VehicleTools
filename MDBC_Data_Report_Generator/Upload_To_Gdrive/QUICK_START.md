# Quick Start - Split & Merge

## In Python (Report Generator):

1. Load CSV, scan dives, select dives (as usual)
2. **☑ Check "Split into separate files (one per dive)"**
3. Generate Report
4. Find files: `Report_DIVE###_N.docx` in output folder

## In Apps Script:

1. Open web app URL
2. **Upload:** Drag all DIVE###_*.docx files → Click "Upload All Files"
3. **Convert:** Click "Start Converting" → Click "Continue Converting" if needed
4. **Merge:** Click "Start Merge" → Click "Continue Merge" as needed
5. **Done!** Click link to open merged document

## Checkpoints:

- **"Continue Converting"** appears if timeout approaching during conversion
- **"Continue Merge"** appears if timeout approaching during merge
- Keep clicking until you see "✅ Complete!"

## Typical Timeline:

- 10 dives = ~30 minutes total
- 20 dives = ~60-80 minutes total
- Mostly hands-off, just click "Continue" buttons every 5 minutes

## After Merge:

- Open merged Google Doc
- Share with team
- Download as PDF if needed
- Delete original .docx chunks

---

**Files created:**
- `Code_Batch_Merge.gs` - Apps Script backend
- `index_batch.html` - Web interface
- `SPLIT_MERGE_SETUP.md` - Detailed setup guide
- `SPLIT_MERGE_FEASIBILITY.md` - Technical analysis

**Python changes:**
- Added `generate_report_chunks()` method
- Added `split_by_dive` parameter to `generate_report()`
- Added checkbox in GUI

**Ready to test!**
