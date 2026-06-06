/**
 * Google Apps Script - Batch Upload, Convert & Merge for Split Reports
 * 
 * This script handles uploading multiple .docx files, converting them to Google Docs,
 * and merging them in order. Uses manual checkpoints to work around 6-minute timeout.
 * 
 * SETUP:
 * 1. Enable "Google Drive API" (v2) service in Apps Script
 * 2. Add required OAuth scopes to appsscript.json manifest (see documentation)
 * 3. Deploy as web app or use from HTML interface
 */

// ==================================================================
// GLOBAL STATE MANAGEMENT (using Properties Service for persistence)
// ==================================================================

function getMergeState() {
  var props = PropertiesService.getUserProperties();
  var stateJson = props.getProperty('MERGE_STATE');
  
  if (stateJson) {
    return JSON.parse(stateJson);
  }
  
  return {
    step: 'idle',  // idle, uploading, converting, merging, complete
    uploadedFiles: [],
    convertedDocs: [],
    masterDocId: null,
    currentMergeIndex: 0,
    totalChunks: 0,
    startTime: null
  };
}

function saveMergeState(state) {
  var props = PropertiesService.getUserProperties();
  props.setProperty('MERGE_STATE', JSON.stringify(state));
  Logger.log('State saved: ' + state.step);
}

function clearMergeState() {
  var props = PropertiesService.getUserProperties();
  props.deleteProperty('MERGE_STATE');
  Logger.log('State cleared');
}

// ==================================================================
// STEP 1: UPLOAD FILES
// ==================================================================

function startBatchUpload(filesData, folderId) {
  /**
   * Upload multiple .docx files to Google Drive
   * filesData: Array of {name: string, data: base64}
   * Returns: {success: boolean, uploadedFiles: array}
   */
  try {
    Logger.log('==============================================');
    Logger.log('startBatchUpload CALLED');
    Logger.log('==============================================');
    Logger.log('Number of files received: ' + filesData.length);
    Logger.log('Folder ID: ' + (folderId || 'none (root)'));
    Logger.log('Type of filesData: ' + typeof filesData);
    Logger.log('Is filesData an array: ' + Array.isArray(filesData));
    
    var state = getMergeState();
    Logger.log('Current state: ' + JSON.stringify(state));
    
    // Initialize state on first batch, append on subsequent batches
    if (state.step === 'idle' || !state.uploadedFiles) {
      state.step = 'uploading';
      state.uploadedFiles = [];
      state.totalChunks = 0;
      state.startTime = new Date().toISOString();
      // Save the folder ID so conversion step can reference it later
      state.uploadFolderId = folderId;
    }
    
    saveMergeState(state);
    
    // Handle folder ID - check for empty string, null, or undefined
    // Also extract ID from full Google Drive URLs
    var folder;
    if (folderId && typeof folderId === 'string' && folderId.trim() !== '') {
      var cleanFolderId = folderId.trim();
      
      // Extract folder ID from URL if full URL was provided
      // Format: https://drive.google.com/drive/folders/FOLDER_ID or
      //         https://drive.google.com/drive/folders/FOLDER_ID?usp=...
      if (cleanFolderId.indexOf('drive.google.com') > -1) {
        var match = cleanFolderId.match(/\/folders\/([a-zA-Z0-9_-]+)/);
        if (match && match[1]) {
          cleanFolderId = match[1];
          Logger.log('Extracted folder ID from URL: ' + cleanFolderId);
        } else {
          throw new Error('Could not extract folder ID from URL: ' + folderId);
        }
      }
      
      Logger.log('Using specified folder ID: ' + cleanFolderId);
      try {
        folder = DriveApp.getFolderById(cleanFolderId);
      } catch (e) {
        Logger.log('Error getting folder by ID: ' + e.toString());
        throw new Error('Invalid folder ID: ' + cleanFolderId + '. Make sure you have access to this folder.');
      }
    } else {
      Logger.log('Using My Drive root folder');
      folder = DriveApp.getRootFolder();
    }
    Logger.log('Target folder: ' + folder.getName());
    var uploadedFiles = [];
    
    for (var i = 0; i < filesData.length; i++) {
      var fileData = filesData[i];
      
      // Remove data URL prefix if present
      var base64Data = fileData.data;
      if (base64Data.indexOf(',') > -1) {
        base64Data = base64Data.split(',')[1];
      }
      
      // Decode and create blob
      var decoded = Utilities.base64Decode(base64Data);
      var blob = Utilities.newBlob(
        decoded,
        'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
        fileData.name
      );
      
      // Upload as .docx (don't convert yet)
      var file = folder.createFile(blob);
      
      uploadedFiles.push({
        id: file.getId(),
        name: file.getName(),
        url: file.getUrl()
      });
      
      Logger.log('Uploaded: ' + fileData.name + ' (' + (i+1) + '/' + filesData.length + ')');
    }
    
    // Append to existing uploaded files (don't replace!)
    state.uploadedFiles = state.uploadedFiles.concat(uploadedFiles);
    state.totalChunks = state.uploadedFiles.length;  // Update total
    state.step = 'uploading';  // Keep in uploading state until client says all batches done
    saveMergeState(state);
    
    Logger.log('Total files uploaded so far: ' + state.uploadedFiles.length);
    
    return {
      success: true,
      uploadedFiles: uploadedFiles,  // Return just this batch
      totalUploaded: state.uploadedFiles.length,  // Return cumulative total
      message: uploadedFiles.length + ' files uploaded (total: ' + state.uploadedFiles.length + ')'
    };
    
  } catch (error) {
    Logger.log('Upload error: ' + error.toString());
    return {
      success: false,
      error: error.toString()
    };
  }
}

// ==================================================================
// MARK UPLOAD COMPLETE (after all batches)
// ==================================================================

function markUploadComplete() {
  /**
   * Call this after all upload batches are complete
   */
  try {
    var state = getMergeState();
    state.step = 'uploaded';
    saveMergeState(state);
    
    Logger.log('Upload marked complete. Total files: ' + state.uploadedFiles.length);
    
    return {
      success: true,
      totalFiles: state.uploadedFiles.length
    };
  } catch (error) {
    Logger.log('Error marking upload complete: ' + error.toString());
    return {
      success: false,
      error: error.toString()
    };
  }
}

// ==================================================================
// STEP 2: CONVERT TO GOOGLE DOCS
// ==================================================================

function convertFromFolder(folderId) {
  /**
   * Load .docx files from an existing folder and convert them
   * This allows jumping into the workflow at Step 2
   */
  try {
    var state = getMergeState();
    
    // Parse folder ID from URL if needed
    var cleanFolderId = folderId.trim();
    if (cleanFolderId.indexOf('drive.google.com') > -1) {
      var match = cleanFolderId.match(/\/folders\/([a-zA-Z0-9_-]+)/);
      if (match && match[1]) {
        cleanFolderId = match[1];
        Logger.log('Extracted folder ID from URL: ' + cleanFolderId);
      } else {
        throw new Error('Could not extract folder ID from URL: ' + folderId);
      }
    }
    
    Logger.log('Loading .docx files from folder: ' + cleanFolderId);
    
    var folder;
    try {
      folder = DriveApp.getFolderById(cleanFolderId);
    } catch (e) {
      throw new Error('Invalid folder ID: ' + cleanFolderId + '. Make sure you have access to this folder.');
    }
    
    // Find all .docx files in the folder
    var docxFiles = folder.getFilesByType('application/vnd.openxmlformats-officedocument.wordprocessingml.document');
    var fileList = [];
    
    while (docxFiles.hasNext()) {
      var file = docxFiles.next();
      fileList.push({
        id: file.getId(),
        name: file.getName()
      });
    }
    
    if (fileList.length === 0) {
      return {
        success: false,
        error: 'No .docx files found in the specified folder'
      };
    }
    
    Logger.log('Found ' + fileList.length + ' .docx files');
    
    // Sort by name (ensures DIVE### order)
    fileList.sort(function(a, b) {
      return a.name.localeCompare(b.name);
    });
    
    // Update state to mark these as "uploaded"
    state.uploadedFiles = fileList;
    state.totalChunks = fileList.length;
    state.step = 'uploaded';
    // Save the folder ID so convertUploadedFiles can re-scan for fresh file IDs
    state.uploadFolderId = cleanFolderId;
    saveMergeState(state);
    
    // Now convert them
    return convertUploadedFiles();
    
  } catch (error) {
    Logger.log('Error loading from folder: ' + error.toString());
    return {
      success: false,
      error: error.toString()
    };
  }
}

function convertUploadedFiles() {
  /**
   * Convert uploaded .docx files to Google Docs format
   * Call this AFTER uploads are complete
   * Returns: {success: boolean, convertedDocs: array, timeRemaining: string}
   */
  try {
    var state = getMergeState();
    
    if (state.step !== 'uploaded') {
      return {
        success: false,
        error: 'Must upload files first. Current step: ' + state.step
      };
    }
    
    state.step = 'converting';
    saveMergeState(state);
    
    var convertedDocs = [];
    var startTime = new Date().getTime();
    
    // If files were uploaded to a specific folder, scan that folder for .docx files
    // This is more reliable than using stored file IDs (in case state is stale)
    var sortedFiles;
    if (state.uploadFolderId && state.uploadFolderId.trim() !== '') {
      Logger.log('Files were uploaded to folder ' + state.uploadFolderId + ', scanning folder for .docx files');
      
      var folderId = state.uploadFolderId.trim();
      
      // Extract folder ID from URL if needed
      if (folderId.indexOf('drive.google.com') > -1) {
        var match = folderId.match(/\/folders\/([a-zA-Z0-9_-]+)/);
        if (match && match[1]) {
          folderId = match[1];
        }
      }
      
      try {
        var folder = DriveApp.getFolderById(folderId);
        var docxFiles = folder.getFilesByType('application/vnd.openxmlformats-officedocument.wordprocessingml.document');
        var fileList = [];
        
        while (docxFiles.hasNext()) {
          var file = docxFiles.next();
          fileList.push({
            id: file.getId(),
            name: file.getName()
          });
        }
        
        sortedFiles = fileList.sort(function(a, b) {
          return a.name.localeCompare(b.name);
        });
        
        Logger.log('Found ' + sortedFiles.length + ' .docx files in upload folder');
      } catch (e) {
        Logger.log('Error accessing upload folder, falling back to state: ' + e.toString());
        sortedFiles = state.uploadedFiles.slice().sort(function(a, b) {
          return a.name.localeCompare(b.name);
        });
      }
    } else {
      // No specific folder, use file IDs from state
      sortedFiles = state.uploadedFiles.slice().sort(function(a, b) {
        return a.name.localeCompare(b.name);
      });
    }
    
    for (var i = 0; i < sortedFiles.length; i++) {
      var fileInfo = sortedFiles[i];
      
      Logger.log('Converting file ' + (i+1) + ': ' + fileInfo.name + ' (ID: ' + fileInfo.id + ')');
      
      // Use DriveApp to get file and blob, then Drive API to convert
      try {
        var originalFile = DriveApp.getFileById(fileInfo.id);
        Logger.log('File accessed: ' + originalFile.getName() + ', MIME type: ' + originalFile.getMimeType());
        
        // Get the file's blob content
        var blob = originalFile.getBlob();
        var convertedDocName = fileInfo.name.replace('.docx', '');
        
        // Use Drive.Files.insert WITHOUT specifying parent - goes to My Drive root
        // This avoids folder permission issues
        var fileMetadata = {
          title: convertedDocName,
          mimeType: 'application/vnd.google-apps.document'
        };
        
        var convertedFile = Drive.Files.insert(fileMetadata, blob, {
          convert: true
        });
        
        Logger.log('Successfully converted: ' + convertedFile.title + ' (ID: ' + convertedFile.id + ')');
        
        // Now move it to the same folder as the original using DriveApp
        var parents = originalFile.getParents();
        if (parents.hasNext()) {
          var targetFolder = parents.next();
          var convertedDriveFile = DriveApp.getFileById(convertedFile.id);
          targetFolder.addFile(convertedDriveFile);
          DriveApp.getRootFolder().removeFile(convertedDriveFile);
          Logger.log('Moved converted file to folder: ' + targetFolder.getName());
        }
        
        convertedDocs.push({
          id: convertedFile.id,
          name: convertedFile.title,
          url: convertedFile.alternateLink
        });
      } catch (convertError) {
        Logger.log('ERROR converting file: ' + convertError.toString());
        Logger.log('File ID that failed: ' + fileInfo.id);
        Logger.log('File name: ' + fileInfo.name);
        throw new Error('Failed to convert ' + fileInfo.name + ': ' + convertError.toString());
      }
      
      // Check time - if approaching 5 minutes, pause
      var elapsedMs = new Date().getTime() - startTime;
      if (elapsedMs > 300000) {  // 5 minutes
        Logger.log('Approaching timeout at ' + (i+1) + '/' + sortedFiles.length + ' conversions');
        
        // Save partial progress
        state.convertedDocs = convertedDocs;
        state.step = 'converting-partial';
        state.partialIndex = i + 1;
        saveMergeState(state);
        
        return {
          success: false,
          partial: true,
          completed: i + 1,
          total: sortedFiles.length,
          message: 'Timeout approaching. Converted ' + (i+1) + ' of ' + sortedFiles.length,
          instruction: 'Click "Continue Converting" to resume'
        };
      }
      
      Logger.log('Converted: ' + fileInfo.name + ' (' + (i+1) + '/' + sortedFiles.length + ')');
    }
    
    state.convertedDocs = convertedDocs;
    state.step = 'converted';
    saveMergeState(state);
    
    return {
      success: true,
      convertedDocs: convertedDocs,
      message: convertedDocs.length + ' documents converted successfully'
    };
    
  } catch (error) {
    Logger.log('Conversion error: ' + error.toString());
    return {
      success: false,
      error: error.toString()
    };
  }
}

function continueConverting() {
  /**
   * Resume conversion if it was paused due to timeout
   */
  try {
    var state = getMergeState();
    
    if (state.step !== 'converting-partial') {
      return {
        success: false,
        error: 'No partial conversion to continue'
      };
    }
    
    var startIndex = state.partialIndex || 0;
    
    // Re-scan folder for fresh file IDs if files were uploaded to a specific folder
    var sortedFiles;
    if (state.uploadFolderId && state.uploadFolderId.trim() !== '') {
      Logger.log('Re-scanning folder for fresh file IDs: ' + state.uploadFolderId);
      
      var folderId = state.uploadFolderId.trim();
      
      // Extract folder ID from URL if needed
      if (folderId.indexOf('drive.google.com') > -1) {
        var match = folderId.match(/\/folders\/([a-zA-Z0-9_-]+)/);
        if (match && match[1]) {
          folderId = match[1];
        }
      }
      
      try {
        var folder = DriveApp.getFolderById(folderId);
        var docxFiles = folder.getFilesByType('application/vnd.openxmlformats-officedocument.wordprocessingml.document');
        var fileList = [];
        
        while (docxFiles.hasNext()) {
          var file = docxFiles.next();
          fileList.push({
            id: file.getId(),
            name: file.getName()
          });
        }
        
        sortedFiles = fileList.sort(function(a, b) {
          return a.name.localeCompare(b.name);
        });
        
        Logger.log('Re-scanned folder, found ' + sortedFiles.length + ' .docx files');
      } catch (e) {
        Logger.log('Error re-scanning folder, using state: ' + e.toString());
        sortedFiles = state.uploadedFiles.slice().sort(function(a, b) {
          return a.name.localeCompare(b.name);
        });
      }
    } else {
      // No specific folder, use file IDs from state
      sortedFiles = state.uploadedFiles.slice().sort(function(a, b) {
        return a.name.localeCompare(b.name);
      });
    }
    
    var convertedDocs = state.convertedDocs || [];
    var startTime = new Date().getTime();
    
    for (var i = startIndex; i < sortedFiles.length; i++) {
      var fileInfo = sortedFiles[i];
      
      Logger.log('Converting file ' + (i+1) + ': ' + fileInfo.name + ' (ID: ' + fileInfo.id + ')');
      
      // Use DriveApp to get file and blob, then Drive API to convert
      try {
        var originalFile = DriveApp.getFileById(fileInfo.id);
        Logger.log('File accessed: ' + originalFile.getName() + ', MIME type: ' + originalFile.getMimeType());
        
        // Get the file's blob content
        var blob = originalFile.getBlob();
        var convertedDocName = fileInfo.name.replace('.docx', '');
        
        // Use Drive.Files.insert WITHOUT specifying parent - goes to My Drive root
        // This avoids folder permission issues
        var fileMetadata = {
          title: convertedDocName,
          mimeType: 'application/vnd.google-apps.document'
        };
        
        var convertedFile = Drive.Files.insert(fileMetadata, blob, {
          convert: true
        });
        
        Logger.log('Successfully converted: ' + convertedFile.title + ' (ID: ' + convertedFile.id + ')');
        
        // Now move it to the same folder as the original using DriveApp
        var parents = originalFile.getParents();
        if (parents.hasNext()) {
          var targetFolder = parents.next();
          var convertedDriveFile = DriveApp.getFileById(convertedFile.id);
          targetFolder.addFile(convertedDriveFile);
          DriveApp.getRootFolder().removeFile(convertedDriveFile);
          Logger.log('Moved converted file to folder: ' + targetFolder.getName());
        }
        
        convertedDocs.push({
          id: convertedFile.id,
          name: convertedFile.title,
          url: convertedFile.alternateLink
        });
      } catch (convertError) {
        Logger.log('ERROR converting file: ' + convertError.toString());
        Logger.log('File ID that failed: ' + fileInfo.id);
        Logger.log('File name: ' + fileInfo.name);
        throw new Error('Failed to convert ' + fileInfo.name + ': ' + convertError.toString());
      }
      
      // Check time again
      var elapsedMs = new Date().getTime() - startTime;
      if (elapsedMs > 300000 && i < sortedFiles.length - 1) {
        Logger.log('Timeout approaching again at ' + (i+1) + '/' + sortedFiles.length);
        
        state.convertedDocs = convertedDocs;
        state.partialIndex = i + 1;
        saveMergeState(state);
        
        return {
          success: false,
          partial: true,
          completed: i + 1,
          total: sortedFiles.length,
          message: 'Converted ' + (i+1) + ' of ' + sortedFiles.length + ' so far',
          instruction: 'Click "Continue Converting" again'
        };
      }
      
      Logger.log('Converted: ' + fileInfo.name + ' (' + (i+1) + '/' + sortedFiles.length + ')');
    }
    
    state.convertedDocs = convertedDocs;
    state.step = 'converted';
    delete state.partialIndex;
    saveMergeState(state);
    
    return {
      success: true,
      convertedDocs: convertedDocs,
      message: 'All ' + convertedDocs.length + ' documents converted!'
    };
    
  } catch (error) {
    return {
      success: false,
      error: error.toString()
    };
  }
}

// ==================================================================
// STEP 3: MERGE DOCUMENTS
// ==================================================================

function startMerge(folderId, sourceFolderId) {
  /**
   * Start merging converted documents
   * Creates master document and begins merge
   * 
   * folderId: Where to save the merged document (optional, defaults to My Drive)
   * sourceFolderId: Optional folder containing already-converted Google Docs to merge
   *                 (allows jumping into workflow at Step 3)
   */
  try {
    var state = getMergeState();
    
    // If sourceFolderId is provided, load Google Docs from that folder
    if (sourceFolderId && typeof sourceFolderId === 'string' && sourceFolderId.trim() !== '') {
      Logger.log('Loading Google Docs from source folder');
      
      var cleanSourceFolderId = sourceFolderId.trim();
      
      // Extract folder ID from URL if needed
      if (cleanSourceFolderId.indexOf('drive.google.com') > -1) {
        var match = cleanSourceFolderId.match(/\/folders\/([a-zA-Z0-9_-]+)/);
        if (match && match[1]) {
          cleanSourceFolderId = match[1];
        } else {
          throw new Error('Could not extract source folder ID from URL');
        }
      }
      
      var sourceFolder;
      try {
        sourceFolder = DriveApp.getFolderById(cleanSourceFolderId);
      } catch (e) {
        throw new Error('Invalid source folder ID: ' + cleanSourceFolderId);
      }
      
      // Get all Google Docs from the folder
      var docsIterator = sourceFolder.getFilesByType('application/vnd.google-apps.document');
      var docsList = [];
      
      while (docsIterator.hasNext()) {
        var doc = docsIterator.next();
        docsList.push({
          id: doc.getId(),
          name: doc.getName(),
          url: doc.getUrl()
        });
      }
      
      if (docsList.length === 0) {
        return {
          success: false,
          error: 'No Google Docs found in the specified source folder'
        };
      }
      
      Logger.log('Found ' + docsList.length + ' Google Docs in source folder');
      
      // Sort by name
      docsList.sort(function(a, b) {
        return a.name.localeCompare(b.name);
      });
      
      // Update state
      state.convertedDocs = docsList;
      state.step = 'converted';
      state.totalChunks = docsList.length;
      saveMergeState(state);
    }
    
    // Check if we have docs to merge
    if (state.step !== 'converted' || !state.convertedDocs || state.convertedDocs.length === 0) {
      return {
        success: false,
        error: 'No converted documents found. Please complete Step 2 first or provide a source folder.'
      };
    }
    
    // Create master document
    var folder;
    if (folderId && typeof folderId === 'string' && folderId.trim() !== '') {
      var cleanFolderId = folderId.trim();
      
      // Extract folder ID from URL if full URL was provided
      if (cleanFolderId.indexOf('drive.google.com') > -1) {
        var match = cleanFolderId.match(/\/folders\/([a-zA-Z0-9_-]+)/);
        if (match && match[1]) {
          cleanFolderId = match[1];
        }
      }
      
      try {
        folder = DriveApp.getFolderById(cleanFolderId);
      } catch (e) {
        throw new Error('Invalid folder ID: ' + cleanFolderId);
      }
    } else {
      folder = DriveApp.getRootFolder();
    }
    var timestamp = Utilities.formatDate(new Date(), Session.getScriptTimeZone(), 'yyyyMMdd_HHmmss');
    var masterDoc = DocumentApp.create('Merged_Report_' + timestamp);
    
    // Move to specified folder
    var masterFile = DriveApp.getFileById(masterDoc.getId());
    folder.addFile(masterFile);
    DriveApp.getRootFolder().removeFile(masterFile);
    
    state.masterDocId = masterDoc.getId();
    state.step = 'merging';
    state.currentMergeIndex = 0;
    saveMergeState(state);
    
    return {
      success: true,
      masterDocId: masterDoc.getId(),
      masterDocUrl: masterDoc.getUrl(),
      message: 'Master document created. Ready to merge.'
    };
    
  } catch (error) {
    return {
      success: false,
      error: error.toString()
    };
  }
}

function continueMerge() {
  /**
   * Merge one chunk at a time to avoid timeout
   * Call repeatedly until complete
   */
  try {
    var state = getMergeState();
    
    if (state.step !== 'merging') {
      return {
        success: false,
        error: 'Merge not started or already complete'
      };
    }
    
    var masterDoc = DocumentApp.openById(state.masterDocId);
    var masterBody = masterDoc.getBody();
    var chunkIndex = state.currentMergeIndex;
    var chunks = state.convertedDocs;
    
    if (chunkIndex >= chunks.length) {
      state.step = 'complete';
      saveMergeState(state);
      
      return {
        success: true,
        complete: true,
        masterDocUrl: masterDoc.getUrl(),
        message: 'Merge complete! All ' + chunks.length + ' chunks merged.'
      };
    }
    
    var startTime = new Date().getTime();
    var mergedCount = 0;
    
    // Merge chunks until timeout approaches
    for (var i = chunkIndex; i < chunks.length; i++) {
      var chunk = chunks[i];
      var sourceDoc = DocumentApp.openById(chunk.id);
      var sourceBody = sourceDoc.getBody();
      
      // Copy all elements from source to master
      var totalElements = sourceBody.getNumChildren();
      
      for (var j = 0; j < totalElements; j++) {
        var element = sourceBody.getChild(j);
        var type = element.getType();
        
        if (type == DocumentApp.ElementType.PARAGRAPH) {
          var para = element.asParagraph().copy();
          masterBody.appendParagraph(para);
        } else if (type == DocumentApp.ElementType.TABLE) {
          var table = element.asTable().copy();
          masterBody.appendTable(table);
        } else if (type == DocumentApp.ElementType.LIST_ITEM) {
          var listItem = element.asListItem().copy();
          masterBody.appendListItem(listItem);
        }
        // Note: InlineImage handled within paragraphs
      }
      
      mergedCount++;
      Logger.log('Merged chunk ' + (i+1) + '/' + chunks.length + ': ' + chunk.name);
      
      // Check if approaching timeout (4.5 minutes)
      var elapsedMs = new Date().getTime() - startTime;
      if (elapsedMs > 270000 && i < chunks.length - 1) {
        state.currentMergeIndex = i + 1;
        saveMergeState(state);
        
        Logger.log('Pausing merge at chunk ' + (i+1) + ' to avoid timeout');
        
        return {
          success: false,
          partial: true,
          completed: i + 1,
          total: chunks.length,
          message: 'Merged ' + (i+1) + ' of ' + chunks.length + ' chunks',
          instruction: 'Click "Continue Merge" to resume',
          masterDocUrl: masterDoc.getUrl()
        };
      }
    }
    
    // All merged!
    state.step = 'complete';
    state.currentMergeIndex = chunks.length;
    saveMergeState(state);
    
    return {
      success: true,
      complete: true,
      masterDocUrl: masterDoc.getUrl(),
      message: 'Merge complete! All ' + chunks.length + ' chunks merged.'
    };
    
  } catch (error) {
    Logger.log('Merge error: ' + error.toString());
    return {
      success: false,
      error: error.toString()
    };
  }
}

// ==================================================================
// STATUS & UTILITY FUNCTIONS
// ==================================================================

function getStatus() {
  /**
   * Get current workflow status
   */
  var state = getMergeState();
  return {
    step: state.step,
    totalChunks: state.totalChunks,
    uploadedCount: state.uploadedFiles ? state.uploadedFiles.length : 0,
    convertedCount: state.convertedDocs ? state.convertedDocs.length : 0,
    mergedCount: state.currentMergeIndex || 0,
    masterDocId: state.masterDocId,
    startTime: state.startTime
  };
}

function resetWorkflow() {
  /**
   * Clear state and start over
   */
  clearMergeState();
  return {
    success: true,
    message: 'Workflow reset. Ready for new upload.'
  };
}

// ==================================================================
// WEB APP INTERFACE
// ==================================================================

function doGet() {
  return HtmlService.createHtmlOutputFromFile('index_batch')
    .setTitle('Batch Upload & Merge - Split Reports')
    .setXFrameOptionsMode(HtmlService.XFrameOptionsMode.ALLOWALL);
}
