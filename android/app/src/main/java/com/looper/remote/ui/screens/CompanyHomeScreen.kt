@file:OptIn(androidx.compose.material3.ExperimentalMaterial3Api::class)

package com.looper.remote.ui.screens

import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.material3.Button
import androidx.compose.material3.Card
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
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp
import androidx.navigation.NavHostController
import com.looper.remote.data.ApiException
import com.looper.remote.data.CompanyInfo
import com.looper.remote.data.OrgNode
import com.looper.remote.ui.Session
import kotlinx.coroutines.launch

@Composable
fun CompanyHomeScreen(nav: NavHostController, host: String, companyId: Int) {
    val company = Session.store.load().firstOrNull { it.host == host && it.companyId == companyId }
    var info by remember { mutableStateOf<CompanyInfo?>(null) }
    var error by remember { mutableStateOf<String?>(null) }
    var instruction by remember { mutableStateOf("") }
    var sending by remember { mutableStateOf(false) }
    val scope = rememberCoroutineScope()

    suspend fun refresh() {
        if (company == null) return
        try {
            info = Session.clientFor(company).me()
        } catch (e: ApiException) {
            if (Session.needsReconnect(e)) {
                nav.navigate("reconnect/$host/$companyId") { popUpTo("switcher") }
            } else {
                error = e.message
            }
        } catch (e: Exception) {
            error = "Could not reach $host."
        }
    }

    LaunchedEffect(host, companyId) { refresh() }

    if (company == null) {
        Text("Company not found.")
        return
    }

    Scaffold(topBar = { TopAppBar(title = { Text(company.companyName) }) }) { padding ->
        Column(modifier = Modifier.fillMaxSize().padding(padding).padding(16.dp)) {
            info?.let { i ->
                Text(
                    "Spend: \$${"%.4f".format(i.spend_usd_total)}" +
                        (i.budget_usd_cap?.let { " / \$${"%.2f".format(it)} cap" } ?: ""),
                    style = MaterialTheme.typography.bodySmall,
                )
                Row(modifier = Modifier.fillMaxWidth().padding(top = 8.dp), horizontalArrangement = Arrangement.SpaceBetween) {
                    Button(onClick = {
                        scope.launch {
                            try {
                                if (i.paused) Session.clientFor(company).resume() else Session.clientFor(company).pause()
                                refresh()
                            } catch (e: Exception) { error = e.message }
                        }
                    }) { Text(if (i.paused) "Resume company" else "Pause company") }
                }

                OutlinedTextField(
                    value = instruction,
                    onValueChange = { instruction = it },
                    label = { Text("Instruct the CEO") },
                    modifier = Modifier.fillMaxWidth().padding(top = 16.dp),
                )
                Button(
                    enabled = !sending && instruction.isNotBlank(),
                    onClick = {
                        sending = true
                        scope.launch {
                            try {
                                Session.clientFor(company).instruct(instruction)
                                instruction = ""
                            } catch (e: Exception) {
                                error = e.message
                            } finally {
                                sending = false
                            }
                        }
                    },
                    modifier = Modifier.fillMaxWidth().padding(top = 8.dp),
                ) { Text(if (sending) "Sending..." else "Send") }

                Row(modifier = Modifier.fillMaxWidth().padding(top = 16.dp), horizontalArrangement = Arrangement.SpaceEvenly) {
                    Text("Activity", modifier = Modifier.clickable { nav.navigate("activity/$host/$companyId") })
                    Text("Approvals", modifier = Modifier.clickable { nav.navigate("approvals/$host/$companyId") })
                    Text("Skills", modifier = Modifier.clickable { nav.navigate("skills/$host/$companyId") })
                    Text("Files", modifier = Modifier.clickable { nav.navigate("files/$host/$companyId") })
                    Text("MCP", modifier = Modifier.clickable { nav.navigate("mcp/$host/$companyId") })
                }

                Text("Org Chart (${i.agent_count}/50)", style = MaterialTheme.typography.titleMedium, modifier = Modifier.padding(top = 16.dp, bottom = 8.dp))
                LazyColumn(modifier = Modifier.fillMaxSize()) {
                    i.org_tree?.let { root -> items(flatten(root)) { (node, depth) ->
                        AgentRow(node, depth) { nav.navigate("agent/$host/$companyId/${node.id}") }
                    } }
                }
            }
            error?.let { Text(it, color = androidx.compose.ui.graphics.Color.Red) }
        }
    }
}

private fun flatten(node: OrgNode, depth: Int = 0): List<Pair<OrgNode, Int>> =
    listOf(node to depth) + node.children.flatMap { flatten(it, depth + 1) }

@Composable
private fun AgentRow(node: OrgNode, depth: Int, onClick: () -> Unit) {
    Card(modifier = Modifier.fillMaxWidth().padding(start = (depth * 16).dp, top = 4.dp, bottom = 4.dp).clickable(onClick = onClick)) {
        Column(modifier = Modifier.padding(12.dp)) {
            Text("${node.name} — ${node.title}", style = MaterialTheme.typography.bodyLarge)
            Text("${node.status}${if (node.is_ceo) " · CEO" else ""}", style = MaterialTheme.typography.bodySmall)
        }
    }
}
