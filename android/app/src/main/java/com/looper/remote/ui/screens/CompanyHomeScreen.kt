@file:OptIn(androidx.compose.material3.ExperimentalMaterial3Api::class)

package com.looper.remote.ui.screens

import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.ArrowBack
import androidx.compose.material.icons.filled.MoreVert
import androidx.compose.material.icons.filled.Refresh
import androidx.compose.material3.Button
import androidx.compose.material3.Card
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.DropdownMenu
import androidx.compose.material3.DropdownMenuItem
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
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
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp
import android.net.Uri
import androidx.navigation.NavHostController
import com.looper.remote.data.ApiError
import com.looper.remote.data.CompanyInfo
import com.looper.remote.data.SavedCompany
import com.looper.remote.ui.Session
import kotlinx.coroutines.launch

@Composable
fun CompanyHomeScreen(nav: NavHostController, host: String, companyId: Int) {
    val scope = rememberCoroutineScope()
    val company = Session.store.load().firstOrNull { it.host == host && it.companyId == companyId }
        ?: run { nav.popBackStack(); return }

    var info by remember { mutableStateOf<CompanyInfo?>(null) }
    var error by remember { mutableStateOf<String?>(null) }
    var instruction by remember { mutableStateOf("") }
    var sending by remember { mutableStateOf(false) }
    var menuExpanded by remember { mutableStateOf(false) }

    fun load() {
        scope.launch {
            try {
                info = Session.clientFor(company).me()
                error = null
            } catch (e: ApiError) {
                if (e.errorKey in listOf("code_changed", "access_disabled", "invalid_token")) {
                    nav.navigate("reconnect/${Uri.encode(host)}/$companyId") { popUpTo("home/${Uri.encode(host)}/$companyId") { inclusive = true } }
                } else error = "Error ${e.code}"
            } catch (e: Exception) { error = e.message }
        }
    }

    LaunchedEffect(Unit) { load() }

    Scaffold(
        topBar = {
            TopAppBar(
                title = { Text(info?.name ?: "Company") },
                navigationIcon = {
                    IconButton(onClick = { nav.popBackStack() }) {
                        Icon(Icons.AutoMirrored.Filled.ArrowBack, contentDescription = "Back")
                    }
                },
                actions = {
                    IconButton(onClick = { load() }) { Icon(Icons.Filled.Refresh, "Refresh") }
                    Box {
                        IconButton(onClick = { menuExpanded = true }) { Icon(Icons.Filled.MoreVert, "Menu") }
                        DropdownMenu(expanded = menuExpanded, onDismissRequest = { menuExpanded = false }) {
                            DropdownMenuItem(text = { Text("Activity / Tasks") }, onClick = { menuExpanded = false; nav.navigate("activity/${Uri.encode(host)}/$companyId") })
                            DropdownMenuItem(text = { Text("Approvals") }, onClick = { menuExpanded = false; nav.navigate("approvals/${Uri.encode(host)}/$companyId") })
                            DropdownMenuItem(text = { Text("Agent Shop") }, onClick = { menuExpanded = false; nav.navigate("agent_shop/${Uri.encode(host)}/$companyId") })
                            DropdownMenuItem(text = { Text("Skill Shop") }, onClick = { menuExpanded = false; nav.navigate("skill_shop/${Uri.encode(host)}/$companyId") })
                            DropdownMenuItem(text = { Text("Models") }, onClick = { menuExpanded = false; nav.navigate("models/${Uri.encode(host)}/$companyId") })
                            DropdownMenuItem(text = { Text("Files") }, onClick = { menuExpanded = false; nav.navigate("files/${Uri.encode(host)}/$companyId") })
                            DropdownMenuItem(text = { Text("MCP Servers") }, onClick = { menuExpanded = false; nav.navigate("mcp/${Uri.encode(host)}/$companyId") })
                            DropdownMenuItem(text = { Text("Settings") }, onClick = { menuExpanded = false; nav.navigate("settings") })
                        }
                    }
                },
            )
        },
    ) { padding ->
        when {
            error != null -> Column(Modifier.fillMaxSize().padding(padding).padding(24.dp), verticalArrangement = Arrangement.Center) {
                Text("Failed to load: $error")
                TextButton(onClick = { load() }) { Text("Retry") }
            }
            info == null -> Box(Modifier.fillMaxSize().padding(padding), contentAlignment = Alignment.Center) { CircularProgressIndicator() }
            else -> {
                val data = info!!
                Column(modifier = Modifier.fillMaxSize().padding(padding).verticalScroll(rememberScrollState()).padding(16.dp)) {
                    Card(modifier = Modifier.fillMaxWidth()) {
                        Column(modifier = Modifier.padding(16.dp)) {
                            Row(horizontalArrangement = Arrangement.SpaceBetween, modifier = Modifier.fillMaxWidth()) {
                                Text("Status", style = MaterialTheme.typography.labelMedium)
                                Text(if (data.paused) "Paused" else "Running", color = if (data.paused) MaterialTheme.colorScheme.error else MaterialTheme.colorScheme.primary)
                            }
                            Row(horizontalArrangement = Arrangement.SpaceBetween, modifier = Modifier.fillMaxWidth()) {
                                Text("Agents", style = MaterialTheme.typography.labelMedium)
                                Text("${data.agentCount}")
                            }
                            Row(horizontalArrangement = Arrangement.SpaceBetween, modifier = Modifier.fillMaxWidth()) {
                                Text("Spend", style = MaterialTheme.typography.labelMedium)
                                Text("$${String.format("%.4f", data.spendUsdTotal)}${data.budgetUsdCap?.let { " / $${"%.2f".format(it)}" } ?: ""}")
                            }
                            Row(modifier = Modifier.padding(top = 10.dp), horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                                if (data.paused) {
                                    Button(onClick = { scope.launch { try { Session.clientFor(company).resume(); load() } catch (_: Exception) {} } }) { Text("Resume") }
                                } else {
                                    Button(onClick = { scope.launch { try { Session.clientFor(company).pause(); load() } catch (_: Exception) {} } }) { Text("Pause") }
                                }
                            }
                        }
                    }
                    Spacer(Modifier.height(12.dp))
                    Card(modifier = Modifier.fillMaxWidth()) {
                        Column(modifier = Modifier.padding(16.dp)) {
                            Text("Instruct CEO", style = MaterialTheme.typography.titleSmall)
                            Spacer(Modifier.height(8.dp))
                            OutlinedTextField(
                                value = instruction,
                                onValueChange = { instruction = it },
                                placeholder = { Text("Give the CEO a new task…") },
                                modifier = Modifier.fillMaxWidth(),
                                minLines = 2,
                            )
                            Spacer(Modifier.height(8.dp))
                            Button(
                                onClick = {
                                    sending = true
                                    scope.launch {
                                        try { Session.clientFor(company).instruct(instruction); instruction = ""; load() }
                                        catch (_: Exception) {}
                                        finally { sending = false }
                                    }
                                },
                                enabled = instruction.isNotBlank() && !sending,
                                modifier = Modifier.fillMaxWidth(),
                            ) { Text("Send to CEO") }
                        }
                    }
                    Spacer(Modifier.height(12.dp))
                    data.orgTree?.let { root ->
                        Card(modifier = Modifier.fillMaxWidth()) {
                            Column(modifier = Modifier.padding(16.dp)) {
                                Text("Organisation", style = MaterialTheme.typography.titleSmall)
                                Spacer(Modifier.height(8.dp))
                                AgentTreeNode(node = root, depth = 0, host = host, nav = nav)
                            }
                        }
                    }
                }
            }
        }
    }
}

@Composable
private fun AgentTreeNode(node: com.looper.remote.data.AgentNode, depth: Int, host: String, nav: NavHostController) {
    Row(
        modifier = Modifier
            .fillMaxWidth()
            .padding(start = (depth * 16).dp, top = 4.dp, bottom = 4.dp)
            .clickable { nav.navigate("agent/${Uri.encode(host)}/${node.id}") },
        verticalAlignment = Alignment.CenterVertically,
        horizontalArrangement = Arrangement.SpaceBetween,
    ) {
        Column(modifier = Modifier.weight(1f)) {
            Text(node.name, style = MaterialTheme.typography.bodyMedium)
            Text(node.title, style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
        }
        Text(node.status, style = MaterialTheme.typography.labelSmall, color = when (node.status) {
            "active" -> MaterialTheme.colorScheme.primary
            "fired" -> MaterialTheme.colorScheme.error
            else -> MaterialTheme.colorScheme.onSurfaceVariant
        })
    }
    node.children.forEach { child -> AgentTreeNode(child, depth + 1, host, nav) }
}
