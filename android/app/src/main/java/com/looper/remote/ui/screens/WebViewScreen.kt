@file:OptIn(androidx.compose.material3.ExperimentalMaterial3Api::class)

package com.looper.remote.ui.screens

import android.app.DownloadManager
import android.content.Context
import android.graphics.Bitmap
import android.net.Uri
import android.os.Environment
import android.webkit.URLUtil
import android.webkit.ValueCallback
import android.webkit.WebChromeClient
import android.webkit.WebResourceError
import android.webkit.WebResourceRequest
import android.webkit.WebSettings
import android.webkit.WebView
import android.webkit.WebViewClient
import android.widget.Toast
import androidx.activity.compose.BackHandler
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Close
import androidx.compose.material.icons.filled.MoreVert
import androidx.compose.material.icons.filled.Refresh
import androidx.compose.material.icons.outlined.CloudOff
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.Button
import androidx.compose.material3.DropdownMenu
import androidx.compose.material3.DropdownMenuItem
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.LinearProgressIndicator
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.material3.TopAppBar
import androidx.compose.runtime.Composable
import androidx.compose.runtime.DisposableEffect
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import androidx.compose.ui.viewinterop.AndroidView
import com.looper.remote.BuildConfig
import com.looper.remote.UpdateChecker
import com.looper.remote.UpdateInfo
import kotlinx.coroutines.delay
import kotlinx.coroutines.launch

@Composable
fun WebViewScreen(
    serverUrl: String,
    onChangeServer: () -> Unit,
) {
    val context = LocalContext.current
    val scope = rememberCoroutineScope()

    var webViewRef by remember { mutableStateOf<WebView?>(null) }
    var pageTitle by remember { mutableStateOf("Looper") }
    var loadProgress by remember { mutableStateOf(100) }
    var hasError by remember { mutableStateOf(false) }
    var canGoBack by remember { mutableStateOf(false) }
    var menuExpanded by remember { mutableStateOf(false) }

    // Update banner / dialog
    var updateInfo by remember { mutableStateOf<UpdateInfo?>(null) }
    var showUpdateBanner by remember { mutableStateOf(false) }
    var showUpdateDialog by remember { mutableStateOf(false) }
    var downloadingUpdate by remember { mutableStateOf(false) }

    // File chooser for WebView uploads (skill imports etc.)
    var fileChooserCallback by remember { mutableStateOf<ValueCallback<Array<Uri>>?>(null) }
    val filePickerLauncher = rememberLauncherForActivityResult(
        contract = ActivityResultContracts.GetContent(),
    ) { uri ->
        val cb = fileChooserCallback
        fileChooserCallback = null
        cb?.onReceiveValue(if (uri != null) arrayOf(uri) else null)
    }

    BackHandler(enabled = canGoBack) {
        webViewRef?.goBack()
    }

    // Check for updates after a short delay (don't slow initial load)
    LaunchedEffect(Unit) {
        delay(3_000)
        val info = UpdateChecker.checkForUpdate(BuildConfig.VERSION_NAME)
        if (info != null) {
            updateInfo = info
            showUpdateBanner = true
        }
    }

    Scaffold(
        topBar = {
            TopAppBar(
                title = {
                    Text(
                        text = pageTitle,
                        maxLines = 1,
                        overflow = TextOverflow.Ellipsis,
                    )
                },
                actions = {
                    IconButton(onClick = { webViewRef?.reload() }) {
                        Icon(Icons.Filled.Refresh, contentDescription = "Refresh")
                    }
                    Box {
                        IconButton(onClick = { menuExpanded = true }) {
                            Icon(Icons.Filled.MoreVert, contentDescription = "Menu")
                        }
                        DropdownMenu(
                            expanded = menuExpanded,
                            onDismissRequest = { menuExpanded = false },
                        ) {
                            DropdownMenuItem(
                                text = { Text("Change Server") },
                                onClick = { menuExpanded = false; onChangeServer() },
                            )
                            DropdownMenuItem(
                                text = { Text("Check for Updates") },
                                onClick = {
                                    menuExpanded = false
                                    scope.launch {
                                        val info = UpdateChecker.checkForUpdate(BuildConfig.VERSION_NAME)
                                        if (info != null) {
                                            updateInfo = info
                                            showUpdateDialog = true
                                        } else {
                                            Toast.makeText(context, "Looper Remote is up to date.", Toast.LENGTH_SHORT).show()
                                        }
                                    }
                                },
                            )
                            DropdownMenuItem(
                                text = { Text("About — v${BuildConfig.VERSION_NAME}") },
                                onClick = { menuExpanded = false },
                                enabled = false,
                            )
                        }
                    }
                },
            )
        },
    ) { innerPadding ->
        Column(modifier = Modifier.fillMaxSize().padding(innerPadding)) {

            // Update banner
            if (showUpdateBanner && updateInfo != null) {
                Surface(
                    color = MaterialTheme.colorScheme.primaryContainer,
                    modifier = Modifier
                        .fillMaxWidth()
                        .clickable { showUpdateDialog = true },
                ) {
                    Row(
                        modifier = Modifier.padding(horizontal = 16.dp, vertical = 8.dp),
                        verticalAlignment = Alignment.CenterVertically,
                    ) {
                        Text(
                            text = "Update available: v${updateInfo!!.version}",
                            modifier = Modifier.weight(1f),
                            style = MaterialTheme.typography.bodyMedium,
                        )
                        TextButton(onClick = { showUpdateDialog = true }) { Text("Update") }
                        IconButton(onClick = { showUpdateBanner = false }) {
                            Icon(Icons.Filled.Close, contentDescription = "Dismiss banner")
                        }
                    }
                }
            }

            // Loading progress bar
            if (loadProgress < 100) {
                LinearProgressIndicator(
                    progress = { loadProgress / 100f },
                    modifier = Modifier.fillMaxWidth(),
                )
            }

            // Error state
            if (hasError) {
                Column(
                    modifier = Modifier.fillMaxSize().padding(32.dp),
                    horizontalAlignment = Alignment.CenterHorizontally,
                    verticalArrangement = androidx.compose.foundation.layout.Arrangement.Center,
                ) {
                    Icon(
                        Icons.Outlined.CloudOff,
                        contentDescription = null,
                        modifier = Modifier.size(72.dp),
                        tint = MaterialTheme.colorScheme.onSurfaceVariant,
                    )
                    Text(
                        text = "Cannot reach server",
                        style = MaterialTheme.typography.titleLarge,
                        modifier = Modifier.padding(top = 16.dp),
                    )
                    Text(
                        text = serverUrl,
                        style = MaterialTheme.typography.bodySmall,
                        color = MaterialTheme.colorScheme.onSurfaceVariant,
                        textAlign = TextAlign.Center,
                        modifier = Modifier.padding(top = 4.dp, bottom = 24.dp),
                    )
                    Button(onClick = {
                        hasError = false
                        webViewRef?.loadUrl(serverUrl)
                    }) { Text("Retry") }
                    TextButton(onClick = onChangeServer) { Text("Change Server") }
                }
            } else {
                AndroidView(
                    factory = { ctx ->
                        WebView(ctx).also { wv ->
                            wv.settings.apply {
                                javaScriptEnabled = true
                                domStorageEnabled = true
                                allowFileAccess = true
                                loadWithOverviewMode = true
                                useWideViewPort = true
                                builtInZoomControls = false
                                displayZoomControls = false
                                setSupportZoom(true)
                                setSupportMultipleWindows(false)
                                // Allow mixed content so http Looper content always loads
                                @Suppress("DEPRECATION")
                                mixedContentMode = WebSettings.MIXED_CONTENT_ALWAYS_ALLOW
                            }

                            wv.webViewClient = object : WebViewClient() {
                                override fun onPageStarted(view: WebView, url: String?, favicon: Bitmap?) {
                                    loadProgress = 0
                                    hasError = false
                                    canGoBack = view.canGoBack()
                                }

                                override fun onPageFinished(view: WebView, url: String?) {
                                    loadProgress = 100
                                    canGoBack = view.canGoBack()
                                }

                                override fun onReceivedError(
                                    view: WebView,
                                    request: WebResourceRequest,
                                    error: WebResourceError,
                                ) {
                                    if (request.isForMainFrame) {
                                        loadProgress = 100
                                        hasError = true
                                    }
                                }
                            }

                            wv.webChromeClient = object : WebChromeClient() {
                                override fun onProgressChanged(view: WebView, newProgress: Int) {
                                    loadProgress = newProgress
                                }

                                override fun onReceivedTitle(view: WebView, title: String?) {
                                    pageTitle = title?.takeIf { it.isNotBlank() }
                                        ?.removePrefix("Looper — ")
                                        ?: "Looper"
                                }

                                override fun onShowFileChooser(
                                    webView: WebView,
                                    filePathCallback: ValueCallback<Array<Uri>>,
                                    fileChooserParams: FileChooserParams,
                                ): Boolean {
                                    fileChooserCallback = filePathCallback
                                    filePickerLauncher.launch("*/*")
                                    return true
                                }
                            }

                            wv.setDownloadListener { url, _, contentDisposition, mimetype, _ ->
                                val dm = ctx.getSystemService(Context.DOWNLOAD_SERVICE) as DownloadManager
                                val fileName = URLUtil.guessFileName(url, contentDisposition, mimetype)
                                dm.enqueue(
                                    DownloadManager.Request(Uri.parse(url)).apply {
                                        setNotificationVisibility(DownloadManager.Request.VISIBILITY_VISIBLE_NOTIFY_COMPLETED)
                                        setDestinationInExternalPublicDir(Environment.DIRECTORY_DOWNLOADS, fileName)
                                    }
                                )
                                Toast.makeText(ctx, "Downloading $fileName to Downloads", Toast.LENGTH_SHORT).show()
                            }

                            webViewRef = wv
                            wv.loadUrl(serverUrl)
                        }
                    },
                    modifier = Modifier.fillMaxSize(),
                )
            }
        }
    }

    // Update dialog
    if (showUpdateDialog && updateInfo != null) {
        AlertDialog(
            onDismissRequest = { showUpdateDialog = false },
            title = { Text("Update Available — v${updateInfo!!.version}") },
            text = {
                Column {
                    Text(
                        "You are running v${BuildConfig.VERSION_NAME}.",
                        style = MaterialTheme.typography.bodySmall,
                        color = MaterialTheme.colorScheme.onSurfaceVariant,
                    )
                    if (updateInfo!!.changelog.isNotBlank()) {
                        Text(
                            text = updateInfo!!.changelog.take(600),
                            style = MaterialTheme.typography.bodySmall,
                            fontFamily = FontFamily.Monospace,
                            modifier = Modifier
                                .padding(top = 8.dp)
                                .verticalScroll(rememberScrollState()),
                        )
                    }
                }
            },
            confirmButton = {
                Button(
                    onClick = {
                        showUpdateDialog = false
                        showUpdateBanner = false
                        downloadingUpdate = true
                        UpdateChecker.downloadAndInstall(context, updateInfo!!)
                        Toast.makeText(
                            context,
                            "Downloading update — check your notifications for progress.",
                            Toast.LENGTH_LONG,
                        ).show()
                        downloadingUpdate = false
                    },
                    enabled = !downloadingUpdate,
                ) { Text("Update Now") }
            },
            dismissButton = {
                TextButton(onClick = { showUpdateDialog = false; showUpdateBanner = false }) {
                    Text("Later")
                }
            },
        )
    }
}
