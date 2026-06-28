@file:OptIn(androidx.compose.material3.ExperimentalMaterial3Api::class)

package com.looper.remote.ui.screens

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.ArrowBack
import androidx.compose.material.icons.filled.Refresh
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.Button
import androidx.compose.material3.Card
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.DropdownMenuItem
import androidx.compose.material3.ExposedDropdownMenuBox
import androidx.compose.material3.ExposedDropdownMenuDefaults
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.MenuAnchorType
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
import androidx.navigation.NavHostController
import com.looper.remote.data.AgentNode
import com.looper.remote.data.AgentTemplateItem
import com.looper.remote.data.CompanyInfo
import com.looper.remote.ui.Session
import kotlinx.coroutines.launch

@Composable
fun AgentShopScreen(nav: NavHostController, host: String, companyId: Int) {
    val scope = rememberCoroutineScope()
    val company = Session.store.load().firstOrNull { it.host == host && it.companyId == companyId }
        ?: run { nav.popBackStack(); return }
    val client = Session.clientFor(company)

    var templates by remember { mutableStateOf<List<AgentTemplateItem>?>(null) }
    var companyInfo by remember { mutableStateOf<CompanyInfo?>(null) }
    var error by remember { mutableStateOf<String?>(null) }
    var hireTarget by remember { mutableStateOf<AgentTemplateItem?>(null) }

    fun load() = scope.launch {
        try {
            templates = client.listAgentTemplates()
            companyInfo = client.me()
            error = null
        } catch (e: Exception) { error = e.message }
    }

    LaunchedEffect(Unit) { load() }

    Scaffold(
        topBar = {
            TopAppBar(
                title = { Text("Agent Shop") },
                navigationIcon = { IconButton(onClick = { nav.popBackStack() }) { Icon(Icons.AutoMirrored.Filled.ArrowBack, "Back") } },
                actions = { IconButton(onClick = { load() }) { Icon(Icons.Filled.Refresh, "Refresh") } },
            )
        },
    ) { padding ->
        when {
            error != null -> Column(Modifier.fillMaxSize().padding(padding).padding(24.dp), verticalArrangement = Arrangement.Center) { Text("Error: $error") }
            templates == null -> Box(Modifier.fillMaxSize().padding(padding), contentAlignment = Alignment.Center) { CircularProgressIndicator() }
            templates!!.isEmpty() -> Column(Modifier.fillMaxSize().padding(padding).padding(24.dp), verticalArrangement = Arrangement.Center, horizontalAlignment = Alignment.CenterHorizontally) { Text("No agent templates available.") }
            else -> LazyColumn(modifier = Modifier.fillMaxSize().padding(padding).padding(12.dp)) {
                items(templates!!) { template ->
                    Card(modifier = Modifier.fillMaxWidth().padding(vertical = 5.dp)) {
                        Column(modifier = Modifier.padding(14.dp)) {
                            Text(template.name, style = MaterialTheme.typography.titleSmall)
                            Text(template.title, style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.primary)
                            if (template.personality.isNotBlank()) {
                                Spacer(Modifier.height(4.dp))
                                Text(template.personality.take(150), style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
                            }
                            Spacer(Modifier.height(8.dp))
                            Button(onClick = { hireTarget = template }, modifier = Modifier.fillMaxWidth()) {
                                Text("Hire this agent")
                            }
                        }
                    }
                }
            }
        }
    }

    hireTarget?.let { template ->
        HireFromTemplateDialog(
            template = template,
            orgTree = companyInfo?.orgTree,
            onDismiss = { hireTarget = null },
            onHire = { parentId, name, title, personality, modelId ->
                scope.launch {
                    try {
                        client.hireAgent(parentId, name, title, personality, modelId)
                        hireTarget = null
                        load()
                    } catch (e: Exception) { error = e.message; hireTarget = null }
                }
            },
        )
    }
}

@Composable
private fun HireFromTemplateDialog(
    template: AgentTemplateItem,
    orgTree: AgentNode?,
    onDismiss: () -> Unit,
    onHire: (parentId: Int, name: String, title: String, personality: String, modelId: String) -> Unit,
) {
    var name by remember { mutableStateOf(template.name) }
    var title by remember { mutableStateOf(template.title) }
    var modelId by remember { mutableStateOf(template.recommendedModelId ?: "anthropic/claude-3-5-haiku") }
    var selectedParent by remember { mutableStateOf<AgentNode?>(orgTree) }
    var parentExpanded by remember { mutableStateOf(false) }

    // Flatten the org tree to a list for the dropdown
    fun flatten(node: AgentNode?): List<AgentNode> {
        if (node == null) return emptyList()
        return listOf(node) + node.children.filter { it.status == "active" }.flatMap { flatten(it) }
    }
    val allAgents = flatten(orgTree)

    AlertDialog(
        onDismissRequest = onDismiss,
        title = { Text("Hire — ${template.name}") },
        text = {
            Column {
                OutlinedTextField(value = name, onValueChange = { name = it }, label = { Text("Name") }, modifier = Modifier.fillMaxWidth(), singleLine = true)
                Spacer(Modifier.height(8.dp))
                OutlinedTextField(value = title, onValueChange = { title = it }, label = { Text("Title") }, modifier = Modifier.fillMaxWidth(), singleLine = true)
                Spacer(Modifier.height(8.dp))
                OutlinedTextField(value = modelId, onValueChange = { modelId = it }, label = { Text("Model ID") }, modifier = Modifier.fillMaxWidth(), singleLine = true)
                Spacer(Modifier.height(8.dp))
                if (allAgents.isNotEmpty()) {
                    ExposedDropdownMenuBox(expanded = parentExpanded, onExpandedChange = { parentExpanded = it }) {
                        OutlinedTextField(
                            value = selectedParent?.name ?: "Select parent agent",
                            onValueChange = {},
                            readOnly = true,
                            label = { Text("Reports to") },
                            trailingIcon = { ExposedDropdownMenuDefaults.TrailingIcon(parentExpanded) },
                            modifier = Modifier.menuAnchor(MenuAnchorType.PrimaryNotEditable).fillMaxWidth(),
                        )
                        ExposedDropdownMenu(expanded = parentExpanded, onDismissRequest = { parentExpanded = false }) {
                            allAgents.forEach { agent ->
                                DropdownMenuItem(
                                    text = { Text("${agent.name} — ${agent.title}") },
                                    onClick = { selectedParent = agent; parentExpanded = false },
                                )
                            }
                        }
                    }
                }
            }
        },
        confirmButton = {
            Button(
                onClick = {
                    val parent = selectedParent ?: return@Button
                    onHire(parent.id, name, title, template.personality, modelId)
                },
                enabled = name.isNotBlank() && selectedParent != null,
            ) { Text("Hire") }
        },
        dismissButton = { TextButton(onClick = onDismiss) { Text("Cancel") } },
    )
}
