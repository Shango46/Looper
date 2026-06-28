@file:OptIn(androidx.compose.material3.ExperimentalMaterial3Api::class)

package com.looper.remote.ui.screens

import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.material3.Button
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Text
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
import androidx.compose.ui.unit.dp
import androidx.navigation.NavHostController
import com.looper.remote.data.ApiException
import com.looper.remote.data.ChatMessage
import kotlinx.coroutines.delay
import kotlinx.coroutines.launch
import com.looper.remote.ui.Session

@Composable
fun AgentChatScreen(nav: NavHostController, host: String, companyId: Int, agentId: Int) {
    val company = Session.store.load().firstOrNull { it.host == host && it.companyId == companyId } ?: run {
        Text("Company not found.")
        return
    }
    var messages by remember { mutableStateOf<List<ChatMessage>>(emptyList()) }
    var busy by remember { mutableStateOf(false) }
    var input by remember { mutableStateOf("") }
    var error by remember { mutableStateOf<String?>(null) }
    val scope = rememberCoroutineScope()

    suspend fun refresh() {
        try {
            val thread = Session.clientFor(company).getChat(agentId)
            messages = thread.messages
            busy = thread.busy
        } catch (e: ApiException) {
            if (Session.needsReconnect(e)) nav.navigate("reconnect/$host/$companyId") { popUpTo("switcher") }
            else error = e.message
        } catch (e: Exception) {
            error = "Could not reach $host."
        }
    }

    LaunchedEffect(agentId) {
        refresh()
        while (true) {
            delay(3000)
            if (busy) refresh()
        }
    }

    Scaffold(topBar = { TopAppBar(title = { Text("Chat") }) }) { padding ->
        Column(modifier = Modifier.fillMaxSize().padding(padding).padding(12.dp)) {
            LazyColumn(modifier = Modifier.weight(1f)) {
                items(messages) { m ->
                    Text(
                        "${if (m.role == "user") "You" else "Agent"}: ${m.content}",
                        style = MaterialTheme.typography.bodyMedium,
                        modifier = Modifier.padding(vertical = 4.dp),
                    )
                }
                if (busy) item { Text("Replying...", style = MaterialTheme.typography.bodySmall) }
            }
            error?.let { Text(it, color = Color.Red) }
            Row(modifier = Modifier.fillMaxWidth().padding(top = 8.dp)) {
                OutlinedTextField(
                    value = input,
                    onValueChange = { input = it },
                    label = { Text("Message") },
                    modifier = Modifier.weight(1f),
                )
                Button(
                    enabled = !busy && input.isNotBlank(),
                    onClick = {
                        val toSend = input
                        input = ""
                        scope.launch {
                            try {
                                Session.clientFor(company).sendChat(agentId, toSend)
                                refresh()
                            } catch (e: Exception) {
                                error = e.message
                            }
                        }
                    },
                    modifier = Modifier.padding(start = 8.dp),
                ) { Text("Send") }
            }
        }
    }
}
