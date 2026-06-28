@file:OptIn(androidx.compose.material3.ExperimentalMaterial3Api::class)

package com.looper.remote.ui.screens

import android.net.Uri
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.UploadFile
import androidx.compose.material3.Button
import androidx.compose.material3.Card
import androidx.compose.material3.FloatingActionButton
import androidx.compose.material3.Icon
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.material3.TopAppBar
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.unit.dp
import androidx.compose.ui.window.Dialog
import androidx.navigation.NavHostController
import com.looper.remote.data.ApiException
import com.looper.remote.data.FileEntry
import com.looper.remote.ui.Session
import kotlinx.coroutines.launch

private data class PendingOp(val sourcePath: String, val isMove: Boolean)

@Composable
fun FileBrowserScreen(nav: NavHostController, host: String, companyId: Int) {
    val company = Session.store.load().firstOrNull { it.host == host && it.companyId == companyId } ?: run {
        Text("Company not found.")
        return
    }
    val context = LocalContext.current
    val scope = rememberCoroutineScope()

    var currentPath by remember { mutableStateOf(".") }
    var entries by remember { mutableStateOf<List<FileEntry>>(emptyList()) }
    var error by remember { mutableStateOf<String?>(null) }
    var pendingOp by remember { mutableStateOf<PendingOp?>(null) }
    var fileMenuTarget by remember { mutableStateOf<String?>(null) }
    var downloadTarget by remember { mutableStateOf<String?>(null) }
    var filterText by remember { mutableStateOf("") }

    fun joinPath(base: String, name: String) = if (base == ".") name else "$base/$name"

    suspend fun refresh() {
        try {
            entries = Session.clientFor(company).listFiles(currentPath)
        } catch (e: ApiException) {
            if (Session.needsReconnect(e)) nav.navigate("reconnect/$host/$companyId") { popUpTo("switcher") }
            else error = e.message
        } catch (e: Exception) {
            error = "Could not reach $host."
        }
    }

    LaunchedEffect(currentPath) { refresh() }

    val uploadLauncher = rememberLauncherForActivityResult(ActivityResultContracts.OpenDocument()) { uri: Uri? ->
        if (uri == null) return@rememberLauncherForActivityResult
        scope.launch {
            try {
                val bytes = context.contentResolver.openInputStream(uri)?.use { it.readBytes() } ?: return@launch
                val filename = uri.lastPathSegment?.substringAfterLast('/') ?: "upload"
                val mimeType = context.contentResolver.getType(uri)
                Session.clientFor(company).uploadFile(currentPath, filename, bytes, mimeType)
                refresh()
            } catch (e: Exception) {
                error = "Upload failed: ${e.message}"
            }
        }
    }

    val downloadLauncher = rememberLauncherForActivityResult(ActivityResultContracts.CreateDocument("*/*")) { uri: Uri? ->
        val target = downloadTarget
        downloadTarget = null
        if (uri == null || target == null) return@rememberLauncherForActivityResult
        scope.launch {
            try {
                context.contentResolver.openOutputStream(uri)?.use { out ->
                    Session.clientFor(company).downloadFile(target, out)
                } ?: throw Exception("Could not open destination for writing")
            } catch (e: Exception) {
                error = "Download failed: ${e.message}"
            }
        }
    }

    Scaffold(
        topBar = { TopAppBar(title = { Text("Files: ${company.companyName}") }) },
        floatingActionButton = {
            FloatingActionButton(onClick = { uploadLauncher.launch(arrayOf("*/*")) }) {
                Icon(Icons.Filled.UploadFile, contentDescription = "Upload")
            }
        },
    ) { padding ->
        Column(modifier = Modifier.fillMaxSize().padding(padding).padding(12.dp)) {
            Breadcrumbs(currentPath, onNavigate = { currentPath = it })

            pendingOp?.let { op ->
                Card(modifier = Modifier.fillMaxWidth().padding(vertical = 6.dp)) {
                    Column(modifier = Modifier.padding(8.dp)) {
                        Text("${if (op.isMove) "Moving" else "Copying"} '${op.sourcePath}' — open the destination folder, then:")
                        Row(modifier = Modifier.fillMaxWidth().padding(top = 8.dp), horizontalArrangement = Arrangement.SpaceBetween) {
                            Button(onClick = {
                                val name = op.sourcePath.substringAfterLast('/')
                                val dst = joinPath(currentPath, name)
                                scope.launch {
                                    try {
                                        if (op.isMove) Session.clientFor(company).moveFile(op.sourcePath, dst)
                                        else Session.clientFor(company).copyFile(op.sourcePath, dst)
                                        pendingOp = null
                                        refresh()
                                    } catch (e: Exception) { error = e.message }
                                }
                            }) { Text("Paste here") }
                            TextButton(onClick = { pendingOp = null }) { Text("Cancel") }
                        }
                    }
                }
            }

            error?.let { Text(it, color = Color.Red, modifier = Modifier.padding(vertical = 4.dp)) }

            OutlinedTextField(
                value = filterText,
                onValueChange = { filterText = it },
                label = { Text("Filter by name") },
                singleLine = true,
                modifier = Modifier.fillMaxWidth().padding(vertical = 6.dp),
            )

            val visibleEntries = if (filterText.isBlank()) entries else entries.filter { it.name.contains(filterText, ignoreCase = true) }

            LazyColumn(modifier = Modifier.fillMaxSize()) {
                items(visibleEntries) { entry ->
                    Card(modifier = Modifier.fillMaxWidth().padding(vertical = 3.dp)) {
                        Row(
                            modifier = Modifier
                                .fillMaxWidth()
                                .padding(10.dp)
                                .clickable {
                                    if (entry.is_dir) currentPath = joinPath(currentPath, entry.name)
                                    else fileMenuTarget = joinPath(currentPath, entry.name)
                                },
                            horizontalArrangement = Arrangement.SpaceBetween,
                        ) {
                            Text("${if (entry.is_dir) "📁" else "📄"} ${entry.name}")
                            if (!entry.is_dir) Text("${entry.size} B", style = MaterialTheme.typography.bodySmall)
                        }
                    }
                }
            }
        }
    }

    fileMenuTarget?.let { target ->
        Dialog(onDismissRequest = { fileMenuTarget = null }) {
            Card {
                Column(modifier = Modifier.padding(16.dp)) {
                    Text(target.substringAfterLast('/'), style = MaterialTheme.typography.titleMedium)
                    Button(
                        onClick = {
                            downloadTarget = target
                            downloadLauncher.launch(target.substringAfterLast('/'))
                            fileMenuTarget = null
                        },
                        modifier = Modifier.fillMaxWidth().padding(top = 8.dp),
                    ) { Text("Download") }
                    Button(
                        onClick = { pendingOp = PendingOp(target, isMove = false); fileMenuTarget = null },
                        modifier = Modifier.fillMaxWidth().padding(top = 8.dp),
                    ) { Text("Copy") }
                    Button(
                        onClick = { pendingOp = PendingOp(target, isMove = true); fileMenuTarget = null },
                        modifier = Modifier.fillMaxWidth().padding(top = 8.dp),
                    ) { Text("Move") }
                    Button(
                        onClick = {
                            scope.launch {
                                try {
                                    Session.clientFor(company).deleteFile(target)
                                    fileMenuTarget = null
                                    refresh()
                                } catch (e: Exception) { error = e.message }
                            }
                        },
                        modifier = Modifier.fillMaxWidth().padding(top = 8.dp),
                    ) { Text("Delete") }
                    TextButton(onClick = { fileMenuTarget = null }, modifier = Modifier.fillMaxWidth().padding(top = 4.dp)) { Text("Cancel") }
                }
            }
        }
    }
}

/** Tappable path segments — "." (root) plus one chip per folder level, each navigating
 * straight to that depth rather than stepping up one level at a time. */
@Composable
private fun Breadcrumbs(currentPath: String, onNavigate: (String) -> Unit) {
    val segments = if (currentPath == ".") emptyList() else currentPath.split("/")
    Row(modifier = Modifier.fillMaxWidth().padding(vertical = 4.dp)) {
        Text(
            "root",
            style = MaterialTheme.typography.bodyMedium,
            color = if (segments.isEmpty()) Color.Unspecified else MaterialTheme.colorScheme.primary,
            modifier = Modifier.clickable { onNavigate(".") },
        )
        var pathSoFar = ""
        segments.forEachIndexed { index, segment ->
            pathSoFar = if (pathSoFar.isEmpty()) segment else "$pathSoFar/$segment"
            val target = pathSoFar
            Text(" / ", style = MaterialTheme.typography.bodyMedium)
            Text(
                segment,
                style = MaterialTheme.typography.bodyMedium,
                color = if (index == segments.lastIndex) Color.Unspecified else MaterialTheme.colorScheme.primary,
                modifier = Modifier.clickable { onNavigate(target) },
            )
        }
    }
}
