@file:OptIn(androidx.compose.material3.ExperimentalMaterial3Api::class)

package com.looper.remote.ui.screens

import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.material3.Button
import androidx.compose.material3.Card
import androidx.compose.material3.MaterialTheme
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
import androidx.compose.ui.unit.dp
import androidx.navigation.NavHostController
import com.looper.remote.data.ApiException
import com.looper.remote.data.TaskDetail
import com.looper.remote.data.TaskSummary
import com.looper.remote.ui.Session
import kotlinx.coroutines.launch

private val LIVE_STATUSES = setOf("pending", "in_progress", "delegated", "awaiting_approval")

@Composable
fun CompanyActivityScreen(nav: NavHostController, host: String, companyId: Int) {
    val company = Session.store.load().firstOrNull { it.host == host && it.companyId == companyId } ?: run {
        Text("Company not found.")
        return
    }
    var tasks by remember { mutableStateOf<List<TaskSummary>>(emptyList()) }
    var selected by remember { mutableStateOf<TaskDetail?>(null) }
    var error by remember { mutableStateOf<String?>(null) }
    val scope = rememberCoroutineScope()

    suspend fun refresh() {
        try {
            tasks = Session.clientFor(company).listTasks()
        } catch (e: ApiException) {
            if (Session.needsReconnect(e)) nav.navigate("reconnect/$host/$companyId") { popUpTo("switcher") }
            else error = e.message
        } catch (e: Exception) {
            error = "Could not reach $host."
        }
    }

    LaunchedEffect(Unit) { refresh() }

    Scaffold(topBar = { TopAppBar(title = { Text("Activity") }) }) { padding ->
        Column(modifier = Modifier.fillMaxSize().padding(padding).padding(12.dp)) {
            error?.let { Text(it, color = androidx.compose.ui.graphics.Color.Red) }
            selected?.let { detail ->
                Card(modifier = Modifier.fillMaxWidth().padding(bottom = 8.dp)) {
                    Column(modifier = Modifier.padding(12.dp)) {
                        Text("Task #${detail.id} — ${detail.status}", style = MaterialTheme.typography.titleSmall)
                        Text(detail.instruction, style = MaterialTheme.typography.bodySmall)
                        detail.result?.let { Text("Result: $it", modifier = Modifier.padding(top = 4.dp)) }
                        if (detail.status in LIVE_STATUSES) {
                            Button(
                                onClick = {
                                    scope.launch {
                                        try {
                                            Session.clientFor(company).cancelTask(detail.id)
                                            selected = Session.clientFor(company).getTask(detail.id)
                                            refresh()
                                        } catch (e: Exception) { error = e.message }
                                    }
                                },
                                modifier = Modifier.padding(top = 8.dp),
                            ) { Text("Cancel") }
                        }
                        Button(onClick = { selected = null }, modifier = Modifier.padding(top = 8.dp)) { Text("Close") }
                    }
                }
            }
            LazyColumn(modifier = Modifier.fillMaxSize()) {
                items(tasks) { t ->
                    Card(
                        modifier = Modifier.fillMaxWidth().padding(vertical = 4.dp).clickable {
                            scope.launch {
                                try { selected = Session.clientFor(company).getTask(t.id) } catch (e: Exception) { error = e.message }
                            }
                        },
                    ) {
                        Column(modifier = Modifier.padding(12.dp)) {
                            Text("#${t.id} — ${t.status} (${t.origin})", style = MaterialTheme.typography.bodyMedium)
                            Text(t.instruction.take(120), style = MaterialTheme.typography.bodySmall)
                        }
                    }
                }
            }
        }
    }
}
