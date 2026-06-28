@file:OptIn(androidx.compose.material3.ExperimentalMaterial3Api::class)

package com.looper.remote.ui.screens

import android.content.ContentValues
import android.content.Context
import android.content.Intent
import android.os.Build
import android.os.Environment
import android.provider.MediaStore
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.heightIn
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.ArrowBack
import androidx.compose.material.icons.filled.CloudUpload
import androidx.compose.material.icons.filled.Folder
import androidx.compose.material.icons.filled.InsertDriveFile
import androidx.compose.material.icons.filled.MoreVert
import androidx.compose.material.icons.filled.Refresh
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.Button
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.DropdownMenu
import androidx.compose.material3.DropdownMenuItem
import androidx.compose.material3.FloatingActionButton
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Scaffold
import androidx.compose.material3.SnackbarHost
import androidx.compose.material3.SnackbarHostState
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.material3.TopAppBar
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateListOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.unit.dp
import androidx.core.content.FileProvider
import androidx.navigation.NavHostController
import com.looper.remote.data.FileEntry
import com.looper.remote.ui.Session
import kotlinx.coroutines.launch
import java.io.File

@Composable
fun FileBrowserScreen(nav: NavHostController, host: String, companyId: Int) {
    val context = LocalContext.current
    val scope = rememberCoroutineScope()
    val snackbar = remember { SnackbarHostState() }

    val company = Session.store.load().firstOrNull { it.host == host && it.companyId == companyId }
        ?: run { nav.popBackStack(); return }
    val client = Session.clientFor(company)

    val pathStack = remember { mutableStateListOf(".") }
    val currentPath = pathStack.last()
    var entries by remember { mutableStateOf<List<FileEntry>?>(null) }
    var error by remember { mutableStateOf<String?>(null) }
    var busy by remember { mutableStateOf(false) }

    // Dialogs
    var renameTarget by remember { mutableStateOf<FileEntry?>(null) }
    var renameValue by remember { mutableStateOf("") }
    var deleteTarget by remember { mutableStateOf<FileEntry?>(null) }
    var viewContent by remember { mutableStateOf<Pair<String, String>?>(null) } // name to text

    fun load() = scope.launch {
        try { entries = client.listFiles(currentPath); error = null }
        catch (e: Exception) { error = e.message }
    }

    LaunchedEffect(currentPath) { load() }

    fun entryPath(entry: FileEntry): String {
        val base = if (currentPath == ".") "" else "$currentPath/"
        return "$base${entry.name}"
    }

    fun doDelete(entry: FileEntry) = scope.launch {
        try {
            client.deleteFile(entryPath(entry))
            load()
            snackbar.showSnackbar("Deleted ${entry.name}")
        } catch (e: Exception) { snackbar.showSnackbar("Delete failed: ${e.message}") }
    }

    fun doRename(entry: FileEntry, newName: String) = scope.launch {
        val src = entryPath(entry)
        val dst = if (currentPath == ".") newName else "$currentPath/$newName"
        try {
            client.moveFile(src, dst)
            load()
            snackbar.showSnackbar("Renamed to $newName")
        } catch (e: Exception) { snackbar.showSnackbar("Rename failed: ${e.message}") }
    }

    fun doDownload(entry: FileEntry) = scope.launch {
        busy = true
        try {
            val (bytes, mime) = client.downloadFileBytes(entryPath(entry))
            val resolvedMime = if (mime == "application/octet-stream") guessMime(entry.name) else mime
            if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.Q) {
                val cv = ContentValues().apply {
                    put(MediaStore.Downloads.DISPLAY_NAME, entry.name)
                    put(MediaStore.Downloads.MIME_TYPE, resolvedMime)
                    put(MediaStore.Downloads.IS_PENDING, 1)
                }
                val uri = context.contentResolver.insert(MediaStore.Downloads.EXTERNAL_CONTENT_URI, cv)
                    ?: throw Exception("Could not create Downloads entry")
                context.contentResolver.openOutputStream(uri)!!.use { it.write(bytes) }
                cv.clear()
                cv.put(MediaStore.Downloads.IS_PENDING, 0)
                context.contentResolver.update(uri, cv, null, null)
            } else {
                val dir = Environment.getExternalStoragePublicDirectory(Environment.DIRECTORY_DOWNLOADS)
                dir.mkdirs()
                File(dir, entry.name).writeBytes(bytes)
            }
            snackbar.showSnackbar("Saved to Downloads/${entry.name}")
        } catch (e: Exception) { snackbar.showSnackbar("Download failed: ${e.message}") }
        finally { busy = false }
    }

    fun doOpen(entry: FileEntry) = scope.launch {
        busy = true
        try {
            val (bytes, mime) = client.downloadFileBytes(entryPath(entry))
            val ext = entry.name.substringAfterLast('.', "")
            val isText = mime.startsWith("text/") || ext in setOf("txt", "md", "json", "yaml", "yml", "toml", "ini", "log", "py", "js", "ts", "kt", "java", "xml", "html", "css", "sh", "bat", "csv")
            if (isText && bytes.size < 512 * 1024) {
                viewContent = entry.name to bytes.decodeToString()
            } else {
                val cache = File(context.cacheDir, "open_${entry.name}")
                cache.writeBytes(bytes)
                val uri = FileProvider.getUriForFile(context, "${context.packageName}.fileprovider", cache)
                val view = Intent(Intent.ACTION_VIEW).apply {
                    setDataAndType(uri, if (mime == "application/octet-stream") guessMime(entry.name) else mime)
                    addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION)
                }
                val chooser = Intent.createChooser(view, "Open ${entry.name} with").apply {
                    addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
                }
                context.startActivity(chooser)
            }
        } catch (e: Exception) { snackbar.showSnackbar("Open failed: ${e.message}") }
        finally { busy = false }
    }

    val filePicker = rememberLauncherForActivityResult(ActivityResultContracts.GetContent()) { uri ->
        if (uri == null) return@rememberLauncherForActivityResult
        scope.launch {
            busy = true
            try {
                val cr = context.contentResolver
                val mime = cr.getType(uri) ?: "application/octet-stream"
                val fileName = cr.query(uri, null, null, null, null)?.use { c ->
                    val idx = c.getColumnIndex(android.provider.OpenableColumns.DISPLAY_NAME)
                    c.moveToFirst(); if (idx >= 0) c.getString(idx) else null
                } ?: uri.lastPathSegment ?: "upload"
                val bytes = cr.openInputStream(uri)!!.use { it.readBytes() }
                client.uploadFile(currentPath, fileName, bytes, mime)
                load()
                snackbar.showSnackbar("Uploaded $fileName")
            } catch (e: Exception) { snackbar.showSnackbar("Upload failed: ${e.message}") }
            finally { busy = false }
        }
    }

    // Rename dialog
    renameTarget?.let { entry ->
        AlertDialog(
            onDismissRequest = { renameTarget = null },
            title = { Text("Rename") },
            text = {
                OutlinedTextField(
                    value = renameValue,
                    onValueChange = { renameValue = it },
                    label = { Text("New name") },
                    singleLine = true,
                )
            },
            confirmButton = {
                Button(onClick = {
                    val name = renameValue.trim()
                    if (name.isNotBlank()) { doRename(entry, name); renameTarget = null }
                }) { Text("Rename") }
            },
            dismissButton = { TextButton(onClick = { renameTarget = null }) { Text("Cancel") } },
        )
    }

    // Delete confirmation dialog
    deleteTarget?.let { entry ->
        AlertDialog(
            onDismissRequest = { deleteTarget = null },
            title = { Text("Delete ${entry.name}?") },
            text = { Text(if (entry.isDir) "This will delete the folder and all its contents." else "This cannot be undone.") },
            confirmButton = {
                Button(onClick = { doDelete(entry); deleteTarget = null },
                    colors = androidx.compose.material3.ButtonDefaults.buttonColors(containerColor = MaterialTheme.colorScheme.error),
                ) { Text("Delete") }
            },
            dismissButton = { TextButton(onClick = { deleteTarget = null }) { Text("Cancel") } },
        )
    }

    // Text file viewer dialog
    viewContent?.let { (name, text) ->
        val scroll = rememberScrollState()
        AlertDialog(
            onDismissRequest = { viewContent = null },
            title = { Text(name) },
            text = {
                Column(modifier = Modifier.heightIn(max = 400.dp).verticalScroll(scroll)) {
                    Text(text, style = MaterialTheme.typography.bodySmall)
                }
            },
            confirmButton = { TextButton(onClick = { viewContent = null }) { Text("Close") } },
        )
    }

    Scaffold(
        snackbarHost = { SnackbarHost(snackbar) },
        topBar = {
            TopAppBar(
                title = { Text(if (currentPath == ".") "Files" else currentPath.substringAfterLast('/')) },
                navigationIcon = {
                    IconButton(onClick = {
                        if (pathStack.size > 1) pathStack.removeLast() else nav.popBackStack()
                    }) { Icon(Icons.AutoMirrored.Filled.ArrowBack, "Back") }
                },
                actions = {
                    if (busy) CircularProgressIndicator(modifier = Modifier.size(24.dp).padding(end = 4.dp))
                    IconButton(onClick = { load() }) { Icon(Icons.Filled.Refresh, "Refresh") }
                },
            )
        },
        floatingActionButton = {
            FloatingActionButton(onClick = { filePicker.launch("*/*") }) {
                Icon(Icons.Filled.CloudUpload, "Upload file")
            }
        },
    ) { padding ->
        when {
            error != null -> Column(Modifier.fillMaxSize().padding(padding).padding(24.dp), verticalArrangement = Arrangement.Center) {
                Text("Error: $error")
                TextButton(onClick = { load() }) { Text("Retry") }
            }
            entries == null -> Box(Modifier.fillMaxSize().padding(padding), contentAlignment = Alignment.Center) { CircularProgressIndicator() }
            entries!!.isEmpty() -> Box(Modifier.fillMaxSize().padding(padding), contentAlignment = Alignment.Center) {
                Text("Empty folder", color = MaterialTheme.colorScheme.onSurfaceVariant)
            }
            else -> LazyColumn(modifier = Modifier.fillMaxSize().padding(padding)) {
                items(entries!!) { entry ->
                    FileRow(
                        entry = entry,
                        onNavigate = { if (entry.isDir) pathStack.add(entryPath(entry)) },
                        onOpen = { doOpen(entry) },
                        onDownload = { doDownload(entry) },
                        onRename = { renameTarget = entry; renameValue = entry.name },
                        onDelete = { deleteTarget = entry },
                    )
                }
            }
        }
    }
}

@Composable
private fun FileRow(
    entry: FileEntry,
    onNavigate: () -> Unit,
    onOpen: () -> Unit,
    onDownload: () -> Unit,
    onRename: () -> Unit,
    onDelete: () -> Unit,
) {
    var menuOpen by remember { mutableStateOf(false) }

    Row(
        modifier = Modifier
            .fillMaxWidth()
            .clickable { onNavigate() }
            .padding(start = 16.dp, end = 4.dp, top = 8.dp, bottom = 8.dp),
        verticalAlignment = Alignment.CenterVertically,
    ) {
        Icon(
            if (entry.isDir) Icons.Filled.Folder else Icons.Filled.InsertDriveFile,
            contentDescription = null,
            tint = if (entry.isDir) MaterialTheme.colorScheme.primary else MaterialTheme.colorScheme.onSurfaceVariant,
        )
        Column(modifier = Modifier.weight(1f).padding(start = 12.dp)) {
            Text(entry.name, style = MaterialTheme.typography.bodyMedium)
            if (!entry.isDir) Text(formatSize(entry.size), style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
        }
        Box {
            IconButton(onClick = { menuOpen = true }) { Icon(Icons.Filled.MoreVert, "Options") }
            DropdownMenu(expanded = menuOpen, onDismissRequest = { menuOpen = false }) {
                if (!entry.isDir) {
                    DropdownMenuItem(text = { Text("Open") }, onClick = { menuOpen = false; onOpen() })
                    DropdownMenuItem(text = { Text("Download") }, onClick = { menuOpen = false; onDownload() })
                }
                DropdownMenuItem(text = { Text("Rename") }, onClick = { menuOpen = false; onRename() })
                DropdownMenuItem(
                    text = { Text("Delete", color = MaterialTheme.colorScheme.error) },
                    onClick = { menuOpen = false; onDelete() },
                )
            }
        }
    }
}

private fun guessMime(name: String): String = when (name.substringAfterLast('.').lowercase()) {
    "pdf" -> "application/pdf"
    "jpg", "jpeg" -> "image/jpeg"
    "png" -> "image/png"
    "gif" -> "image/gif"
    "mp4" -> "video/mp4"
    "mp3" -> "audio/mpeg"
    "txt", "log" -> "text/plain"
    "json" -> "application/json"
    "xml" -> "text/xml"
    "html", "htm" -> "text/html"
    "zip" -> "application/zip"
    else -> "application/octet-stream"
}

private fun formatSize(bytes: Long) = when {
    bytes < 1024 -> "$bytes B"
    bytes < 1024 * 1024 -> "${"%.1f".format(bytes / 1024.0)} KB"
    else -> "${"%.1f".format(bytes / (1024.0 * 1024))} MB"
}
