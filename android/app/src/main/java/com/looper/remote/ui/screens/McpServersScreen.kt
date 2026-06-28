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
import androidx.compose.material3.Card
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
import androidx.compose.ui.unit.dp
import androidx.navigation.NavHostController
import com.looper.remote.data.ApiException
import com.looper.remote.data.McpServerSummary
import com.looper.remote.ui.Session
import kotlinx.coroutines.launch

@Composable
fun McpServersScreen(nav: NavHostController, host: String, companyId: Int) {
    val company = Session.store.load().firstOrNull { it.host == host && it.companyId == companyId } ?: run {
        Text("Company not found.")
        return
    }
    var servers by remember { mutableStateOf<List<McpServerSummary>>(emptyList()) }
    var error by remember { mutableStateOf<String?>(null) }
    var adding by remember { mutableStateOf(false) }
    val scope = rememberCoroutineScope()

    suspend fun refresh() {
        try {
            servers = Session.clientFor(company).listMcpServers()
        } catch (e: ApiException) {
            if (Session.needsReconnect(e)) nav.navigate("reconnect/$host/$companyId") { popUpTo("switcher") }
            else error = e.message
        } catch (e: Exception) {
            error = "Could not reach $host."
        }
    }

    LaunchedEffect(Unit) { refresh() }

    Scaffold(topBar = { TopAppBar(title = { Text("MCP Servers") }) }) { padding ->
        Column(modifier = Modifier.fillMaxSize().padding(padding).padding(12.dp)) {
            Text(
                "Registered here, every active agent in this company can use these tools automatically.",
                style = MaterialTheme.typography.bodySmall,
            )
            error?.let { Text(it, color = Color.Red, modifier = Modifier.padding(vertical = 4.dp)) }

            Button(onClick = { adding = !adding }, modifier = Modifier.padding(vertical = 8.dp)) {
                Text(if (adding) "Cancel" else "Add MCP server")
            }
            if (adding) {
                AddMcpServerForm(onCreate = { name, transport, command, args, url ->
                    scope.launch {
                        try {
                            Session.clientFor(company).createMcpServer(name, transport, command, args, url, emptyMap())
                            adding = false
                            refresh()
                        } catch (e: Exception) { error = e.message }
                    }
                })
            }

            LazyColumn(modifier = Modifier.fillMaxSize()) {
                items(servers) { s ->
                    Card(modifier = Modifier.fillMaxWidth().padding(vertical = 4.dp)) {
                        Column(modifier = Modifier.padding(12.dp)) {
                            Text("${s.name} (${s.transport}) — ${if (s.enabled) "enabled" else "disabled"}", style = MaterialTheme.typography.bodyLarge)
                            Text(
                                "${s.tool_count} tool(s)" + (s.tools_refreshed_at?.let { ", refreshed $it" } ?: ", never refreshed"),
                                style = MaterialTheme.typography.bodySmall,
                            )
                            Row(modifier = Modifier.padding(top = 8.dp)) {
                                TextButton(onClick = {
                                    scope.launch {
                                        try { Session.clientFor(company).refreshMcpServer(s.id); refresh() } catch (e: Exception) { error = e.message }
                                    }
                                }) { Text("Refresh tools") }
                                TextButton(onClick = {
                                    scope.launch {
                                        try { Session.clientFor(company).toggleMcpServer(s.id); refresh() } catch (e: Exception) { error = e.message }
                                    }
                                }) { Text(if (s.enabled) "Disable" else "Enable") }
                                TextButton(onClick = {
                                    scope.launch {
                                        try { Session.clientFor(company).deleteMcpServer(s.id); refresh() } catch (e: Exception) { error = e.message }
                                    }
                                }) { Text("Delete") }
                            }
                        }
                    }
                }
            }
        }
    }
}

private data class McpCatalogEntry(val name: String, val command: String, val args: String)

private val MCP_CATALOG = listOf(
    McpCatalogEntry("Filesystem", "npx", "-y\n@modelcontextprotocol/server-filesystem\n/path/to/company/folder"),
    McpCatalogEntry("GitHub", "npx", "-y\n@modelcontextprotocol/server-github"),
    McpCatalogEntry("Memory", "npx", "-y\n@modelcontextprotocol/server-memory"),
)

@Composable
private fun AddMcpServerForm(onCreate: (String, String, String?, List<String>, String?) -> Unit) {
    var name by remember { mutableStateOf("") }
    var transport by remember { mutableStateOf("stdio") }
    var command by remember { mutableStateOf("") }
    var argsText by remember { mutableStateOf("") }
    var url by remember { mutableStateOf("") }

    Text("Quick-add (verified npm package names — edit args before saving if needed):", style = MaterialTheme.typography.bodySmall, modifier = Modifier.padding(top = 8.dp))
    Row(modifier = Modifier.fillMaxWidth().padding(top = 4.dp)) {
        MCP_CATALOG.forEach { entry ->
            TextButton(onClick = {
                name = entry.name
                transport = "stdio"
                command = entry.command
                argsText = entry.args
            }) { Text(entry.name) }
        }
    }
    if (transport == "stdio" && argsText.contains("/path/to/company/folder")) {
        Text(
            "Edit the filesystem path above to this company's actual folder before saving.",
            style = MaterialTheme.typography.bodySmall,
            color = androidx.compose.ui.graphics.Color.Red,
        )
    }

    OutlinedTextField(name, { name = it }, label = { Text("Name") }, modifier = Modifier.fillMaxWidth().padding(top = 8.dp))
    Row(modifier = Modifier.fillMaxWidth().padding(top = 8.dp)) {
        TextButton(onClick = { transport = "stdio" }) { Text(if (transport == "stdio") "● stdio" else "○ stdio") }
        TextButton(onClick = { transport = "streamable_http" }) { Text(if (transport == "streamable_http") "● streamable_http" else "○ streamable_http") }
    }
    if (transport == "stdio") {
        OutlinedTextField(command, { command = it }, label = { Text("Command (e.g. npx)") }, modifier = Modifier.fillMaxWidth().padding(top = 8.dp))
        OutlinedTextField(argsText, { argsText = it }, label = { Text("Args (one per line)") }, modifier = Modifier.fillMaxWidth().padding(top = 8.dp))
    } else {
        OutlinedTextField(url, { url = it }, label = { Text("URL") }, modifier = Modifier.fillMaxWidth().padding(top = 8.dp))
    }
    Button(
        enabled = name.isNotBlank() && (if (transport == "stdio") command.isNotBlank() else url.isNotBlank()),
        onClick = {
            val args = argsText.lines().map { it.trim() }.filter { it.isNotEmpty() }
            onCreate(name, transport, command.ifBlank { null }, args, url.ifBlank { null })
        },
        modifier = Modifier.fillMaxWidth().padding(top = 8.dp),
    ) { Text("Add server") }
}
