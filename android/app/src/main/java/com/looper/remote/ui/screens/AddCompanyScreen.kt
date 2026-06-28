@file:OptIn(androidx.compose.material3.ExperimentalMaterial3Api::class)

package com.looper.remote.ui.screens

import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.material3.Button
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
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.unit.dp
import androidx.navigation.NavHostController
import com.looper.remote.data.ApiException
import com.looper.remote.data.LooperApiClient
import com.looper.remote.data.SavedCompany
import com.looper.remote.ui.Session
import kotlinx.coroutines.launch

@Composable
fun AddCompanyScreen(nav: NavHostController) {
    val context = LocalContext.current
    var host by remember { mutableStateOf("") }
    var code by remember { mutableStateOf("") }
    var error by remember { mutableStateOf<String?>(null) }
    var connecting by remember { mutableStateOf(false) }
    val scope = rememberCoroutineScope()

    Scaffold(topBar = { TopAppBar(title = { Text("Add Company") }) }) { padding ->
        Column(modifier = Modifier.fillMaxWidth().padding(padding).padding(24.dp)) {
            Text("Get the host (Tailscale IP/name) and 8-character code from the Looper PC's company settings page.")
            OutlinedTextField(
                value = host,
                onValueChange = { host = it },
                label = { Text("Host (e.g. 100.x.x.x)") },
                modifier = Modifier.fillMaxWidth().padding(top = 16.dp),
            )
            OutlinedTextField(
                value = code,
                onValueChange = { code = it.uppercase().take(8) },
                label = { Text("8-character code") },
                modifier = Modifier.fillMaxWidth().padding(top = 12.dp),
            )
            error?.let { Text(it, color = androidx.compose.ui.graphics.Color.Red, modifier = Modifier.padding(top = 8.dp)) }
            Button(
                enabled = !connecting && host.isNotBlank() && code.length == 8,
                onClick = {
                    error = null
                    connecting = true
                    scope.launch {
                        try {
                            val client = LooperApiClient(host.trim())
                            val resp = client.connect(code)
                            val saved = SavedCompany(host.trim(), resp.company_id, resp.company_name, resp.token)
                            Session.store.upsert(saved)
                            Session.syncPollingService(context)
                            nav.navigate("home/${saved.host}/${saved.companyId}") {
                                popUpTo("switcher")
                            }
                        } catch (e: ApiException) {
                            error = when (e.errorCode) {
                                "invalid_code" -> "That code isn't valid for any company on that host."
                                "too_many_attempts" -> "Too many attempts — wait a few minutes and try again."
                                else -> "Connection failed: ${e.message}"
                            }
                        } catch (e: Exception) {
                            error = "Could not reach $host — check the host address and that Looper is running."
                        } finally {
                            connecting = false
                        }
                    }
                },
                modifier = Modifier.fillMaxWidth().padding(top = 16.dp),
            ) {
                Text(if (connecting) "Connecting..." else "Connect")
            }
        }
    }
}
