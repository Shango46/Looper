@file:OptIn(androidx.compose.material3.ExperimentalMaterial3Api::class)

package com.looper.remote.ui.screens

import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.ArrowBack
import androidx.compose.material3.Button
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Text
import androidx.compose.material3.TopAppBar
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.input.KeyboardCapitalization
import androidx.compose.ui.text.input.KeyboardType
import androidx.compose.ui.unit.dp
import androidx.navigation.NavHostController
import com.looper.remote.data.ApiClient
import com.looper.remote.data.SavedCompany
import com.looper.remote.ui.Session
import kotlinx.coroutines.launch

@Composable
fun AddCompanyScreen(nav: NavHostController) {
    val context = LocalContext.current
    val scope = rememberCoroutineScope()
    var host by remember { mutableStateOf("http://") }
    var code by remember { mutableStateOf("") }
    var error by remember { mutableStateOf<String?>(null) }
    var loading by remember { mutableStateOf(false) }

    Scaffold(
        topBar = {
            TopAppBar(
                title = { Text("Add Company") },
                navigationIcon = {
                    IconButton(onClick = { nav.popBackStack() }) {
                        Icon(Icons.AutoMirrored.Filled.ArrowBack, contentDescription = "Back")
                    }
                },
            )
        },
    ) { padding ->
        Column(modifier = Modifier.padding(padding).padding(20.dp)) {
            Text("Enter the Tailscale IP of your Looper PC and the pairing code shown under Company Settings → Remote Access.")
            Spacer(Modifier.height(16.dp))
            OutlinedTextField(
                value = host,
                onValueChange = { host = it; error = null },
                label = { Text("Host (Tailscale IP)") },
                placeholder = { Text("http://100.x.x.x") },
                singleLine = true,
                keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Uri),
                modifier = Modifier.fillMaxWidth(),
            )
            Spacer(Modifier.height(12.dp))
            OutlinedTextField(
                value = code,
                onValueChange = { code = it.uppercase().take(8); error = null },
                label = { Text("Pairing code (8 characters)") },
                singleLine = true,
                keyboardOptions = KeyboardOptions(capitalization = KeyboardCapitalization.Characters),
                modifier = Modifier.fillMaxWidth(),
            )
            if (error != null) {
                Spacer(Modifier.height(8.dp))
                Text(error!!, color = Color(0xFFE53935))
            }
            Spacer(Modifier.height(16.dp))
            Button(
                onClick = {
                    val rawHost = host.trimEnd('/')
                    val withScheme = if (!rawHost.startsWith("http://") && !rawHost.startsWith("https://")) "http://$rawHost" else rawHost
                    // Auto-append Looper's default port if user didn't include one
                    val hostPart = withScheme.substringAfter("://")
                    val cleanHost = if (':' !in hostPart) "$withScheme:8731" else withScheme
                    val cleanCode = code.trim()
                    if (cleanCode.length != 8) { error = "Code must be 8 characters."; return@Button }
                    loading = true; error = null
                    scope.launch {
                        try {
                            val resp = ApiClient.connect(cleanHost, cleanCode)
                            val company = SavedCompany(cleanHost, resp.companyId, resp.companyName, resp.token)
                            Session.store.save(company)
                            Session.syncPollingService(context)
                            nav.popBackStack()
                        } catch (e: Exception) {
                            error = when {
                                e.message?.contains("401") == true -> "Invalid code — check it and try again."
                                e.message?.contains("429") == true -> "Too many attempts. Wait a minute and retry."
                                else -> "Could not reach server: ${e.message}"
                            }
                        } finally { loading = false }
                    }
                },
                enabled = !loading,
                modifier = Modifier.fillMaxWidth(),
            ) {
                if (loading) CircularProgressIndicator(modifier = Modifier.padding(end = 8.dp).height(20.dp).fillMaxWidth(0.1f))
                Text("Connect")
            }
        }
    }
}
