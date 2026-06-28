@file:OptIn(androidx.compose.material3.ExperimentalMaterial3Api::class)

package com.looper.remote.ui.screens

import android.content.Intent
import android.net.Uri
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.ArrowBack
import androidx.compose.material3.Button
import androidx.compose.material3.ButtonDefaults
import androidx.compose.material3.Card
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Switch
import androidx.compose.material3.Text
import androidx.compose.material3.TopAppBar
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.unit.dp
import androidx.navigation.NavHostController
import com.looper.remote.AppTheme
import com.looper.remote.BuildConfig
import com.looper.remote.ServerPrefs
import com.looper.remote.UpdateChecker
import com.looper.remote.UpdateInfo
import kotlinx.coroutines.launch

private sealed interface UpdateState {
    object Idle : UpdateState
    object Checking : UpdateState
    object UpToDate : UpdateState
    data class Available(val info: UpdateInfo) : UpdateState
    data class Error(val msg: String) : UpdateState
}

@Composable
fun SettingsScreen(nav: NavHostController) {
    val context = LocalContext.current
    val scope = rememberCoroutineScope()
    var isDark by AppTheme.isDark
    var updateState by remember { mutableStateOf<UpdateState>(UpdateState.Idle) }

    Scaffold(
        topBar = {
            TopAppBar(
                title = { Text("Settings") },
                navigationIcon = {
                    IconButton(onClick = { nav.popBackStack() }) {
                        Icon(Icons.AutoMirrored.Filled.ArrowBack, "Back")
                    }
                },
            )
        },
    ) { padding ->
        Column(
            modifier = Modifier
                .fillMaxSize()
                .padding(padding)
                .padding(16.dp),
            verticalArrangement = Arrangement.spacedBy(12.dp),
        ) {
            // App version
            Card(modifier = Modifier.fillMaxWidth()) {
                Column(modifier = Modifier.padding(16.dp)) {
                    Text("App Version", style = MaterialTheme.typography.labelMedium, color = MaterialTheme.colorScheme.onSurfaceVariant)
                    Spacer(Modifier.height(4.dp))
                    Text(BuildConfig.VERSION_NAME, style = MaterialTheme.typography.headlineSmall)
                }
            }

            // Dark mode
            Card(modifier = Modifier.fillMaxWidth()) {
                Row(
                    modifier = Modifier.padding(16.dp).fillMaxWidth(),
                    horizontalArrangement = Arrangement.SpaceBetween,
                    verticalAlignment = Alignment.CenterVertically,
                ) {
                    Text("Dark Mode", style = MaterialTheme.typography.bodyLarge)
                    Switch(
                        checked = isDark,
                        onCheckedChange = {
                            isDark = it
                            ServerPrefs(context).darkMode = it
                        },
                    )
                }
            }

            // Check for updates
            Card(modifier = Modifier.fillMaxWidth()) {
                Column(modifier = Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
                    Text("Updates", style = MaterialTheme.typography.titleSmall)
                    when (val state = updateState) {
                        is UpdateState.Checking -> CircularProgressIndicator(modifier = Modifier.size(24.dp))
                        is UpdateState.UpToDate -> Text("You're up to date.", style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.primary)
                        is UpdateState.Available -> {
                            Text("v${state.info.version} is available!", color = MaterialTheme.colorScheme.primary, style = MaterialTheme.typography.bodyMedium)
                            if (state.info.changelog.isNotBlank()) {
                                Text(state.info.changelog, style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
                                Spacer(Modifier.height(4.dp))
                            }
                            Button(
                                onClick = { UpdateChecker.downloadAndInstall(context, state.info) },
                                modifier = Modifier.fillMaxWidth(),
                            ) { Text("Download & Install") }
                        }
                        is UpdateState.Error -> Text(state.msg, color = MaterialTheme.colorScheme.error, style = MaterialTheme.typography.bodySmall)
                        else -> Unit
                    }
                    if (updateState !is UpdateState.Checking && updateState !is UpdateState.Available) {
                        Button(
                            onClick = {
                                updateState = UpdateState.Checking
                                scope.launch {
                                    try {
                                        val info = UpdateChecker.checkForUpdate(BuildConfig.VERSION_NAME)
                                        updateState = if (info != null) UpdateState.Available(info) else UpdateState.UpToDate
                                    } catch (e: Exception) {
                                        updateState = UpdateState.Error(e.message ?: "Check failed")
                                    }
                                }
                            },
                            modifier = Modifier.fillMaxWidth(),
                        ) { Text("Check for Updates") }
                    }
                }
            }

            // Buy me a coffee
            Card(modifier = Modifier.fillMaxWidth()) {
                Column(modifier = Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
                    Text("Support", style = MaterialTheme.typography.titleSmall)
                    Text("Enjoying Looper? Buy me a coffee!", style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
                    Button(
                        onClick = {
                            context.startActivity(Intent(Intent.ACTION_VIEW, Uri.parse("https://www.buymeacoffee.com/ChristopherCassidy")))
                        },
                        modifier = Modifier.fillMaxWidth(),
                        colors = ButtonDefaults.buttonColors(containerColor = Color(0xFFFFDD00), contentColor = Color.Black),
                    ) { Text("☕  Buy me a coffee") }
                }
            }
        }
    }
}
