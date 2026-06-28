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
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.unit.dp
import androidx.navigation.NavHostController
import com.looper.remote.data.ApiException
import com.looper.remote.data.LooperApiClient
import com.looper.remote.ui.Session
import kotlinx.coroutines.launch

/** Reached when an API call comes back code_changed/access_disabled/invalid_token for a saved
 * company — the PC rotated or disabled the code, so the old token no longer works. Forces
 * re-entry of the new code before the company can be used again. */
@Composable
fun ReconnectScreen(nav: NavHostController, host: String, companyId: Int) {
    val company = Session.store.load().firstOrNull { it.host == host && it.companyId == companyId }
    var code by remember { mutableStateOf("") }
    var error by remember { mutableStateOf<String?>(null) }
    var busy by remember { mutableStateOf(false) }
    val scope = rememberCoroutineScope()

    Scaffold(topBar = { TopAppBar(title = { Text("Reconnect") }) }) { padding ->
        Column(modifier = Modifier.fillMaxWidth().padding(padding).padding(24.dp)) {
            Text(
                "The code for \"${company?.companyName ?: "this company"}\" was changed or disabled on the PC. " +
                    "Enter the new 8-character code to reconnect.",
            )
            OutlinedTextField(
                value = code,
                onValueChange = { code = it.uppercase().take(8) },
                label = { Text("New code") },
                modifier = Modifier.fillMaxWidth().padding(top = 16.dp),
            )
            error?.let { Text(it, color = Color.Red, modifier = Modifier.padding(top = 8.dp)) }
            Button(
                enabled = !busy && code.length == 8 && company != null,
                onClick = {
                    if (company == null) return@Button
                    error = null
                    busy = true
                    scope.launch {
                        try {
                            val client = LooperApiClient(host)
                            val resp = client.connect(code)
                            if (resp.company_id != companyId) {
                                error = "That code belongs to a different company on this host."
                            } else {
                                Session.updateToken(company, resp.token)
                                nav.navigate("home/$host/$companyId") { popUpTo("switcher") }
                            }
                        } catch (e: ApiException) {
                            error = if (e.errorCode == "invalid_code") "That code isn't valid." else "Failed: ${e.message}"
                        } catch (e: Exception) {
                            error = "Could not reach $host."
                        } finally {
                            busy = false
                        }
                    }
                },
                modifier = Modifier.fillMaxWidth().padding(top = 16.dp),
            ) {
                Text(if (busy) "Connecting..." else "Reconnect")
            }
        }
    }
}
