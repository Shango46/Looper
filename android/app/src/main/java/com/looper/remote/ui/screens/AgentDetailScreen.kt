@file:OptIn(androidx.compose.material3.ExperimentalMaterial3Api::class)

package com.looper.remote.ui.screens

import android.net.Uri
import androidx.compose.foundation.horizontalScroll
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
import androidx.compose.material.icons.automirrored.filled.Chat
import androidx.compose.material.icons.filled.Refresh
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.Button
import androidx.compose.material3.Card
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.DropdownMenuItem
import androidx.compose.material3.ExposedDropdownMenuBox
import androidx.compose.material3.ExposedDropdownMenuDefaults
import androidx.compose.material3.FilterChip
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.MenuAnchorType
import androidx.compose.material3.OutlinedButton
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
import com.looper.remote.data.AgentDetail
import com.looper.remote.data.AgentTemplateItem
import com.looper.remote.data.ModelItem
import com.looper.remote.ui.MODEL_CATEGORIES
import com.looper.remote.ui.Session
import com.looper.remote.ui.filterByCategory
import com.looper.remote.ui.modalityCategory
import kotlinx.coroutines.launch

@Composable
fun AgentDetailScreen(nav: NavHostController, host: String, agentId: Int) {
    val scope = rememberCoroutineScope()
    val company = Session.store.load().firstOrNull { it.host == host }
        ?: run { nav.popBackStack(); return }
    val client = Session.clientFor(company)

    var detail by remember { mutableStateOf<AgentDetail?>(null) }
    var models by remember { mutableStateOf<List<ModelItem>>(emptyList()) }
    var templates by remember { mutableStateOf<List<AgentTemplateItem>>(emptyList()) }
    var error by remember { mutableStateOf<String?>(null) }
    var showFireDialog by remember { mutableStateOf(false) }
    var showEditDialog by remember { mutableStateOf(false) }
    var showHireDialog by remember { mutableStateOf(false) }

    fun load() = scope.launch {
        try {
            detail = client.getAgent(agentId)
            if (models.isEmpty()) models = runCatching { client.listModels() }.getOrDefault(emptyList())
            if (templates.isEmpty()) templates = runCatching { client.listAgentTemplates() }.getOrDefault(emptyList())
            error = null
        } catch (e: Exception) { error = e.message }
    }

    LaunchedEffect(Unit) { load() }

    Scaffold(
        topBar = {
            TopAppBar(
                title = { Text(detail?.name ?: "Agent") },
                navigationIcon = { IconButton(onClick = { nav.popBackStack() }) { Icon(Icons.AutoMirrored.Filled.ArrowBack, "Back") } },
                actions = {
                    IconButton(onClick = { nav.navigate("chat/${Uri.encode(host)}/$agentId") }) { Icon(Icons.AutoMirrored.Filled.Chat, "Chat") }
                    IconButton(onClick = { load() }) { Icon(Icons.Filled.Refresh, "Refresh") }
                },
            )
        },
    ) { padding ->
        when {
            error != null -> Column(Modifier.fillMaxSize().padding(padding).padding(24.dp), verticalArrangement = Arrangement.Center) {
                Text("Error: $error")
                TextButton(onClick = { load() }) { Text("Retry") }
            }
            detail == null -> Box(Modifier.fillMaxSize().padding(padding), contentAlignment = Alignment.Center) { CircularProgressIndicator() }
            else -> {
                val d = detail!!
                Column(modifier = Modifier.fillMaxSize().padding(padding).verticalScroll(rememberScrollState()).padding(16.dp)) {
                    Card(modifier = Modifier.fillMaxWidth()) {
                        Column(modifier = Modifier.padding(16.dp)) {
                            InfoRow("Title", d.title)
                            InfoRow("Status", d.status)
                            val modelDisplay = models.firstOrNull { it.id == d.modelId }?.let { m ->
                                val cost = m.pricingPrompt?.toDoubleOrNull()?.let { "\$${fmtPrice(it * 1_000_000)}/1M in" } ?: ""
                                val cat = modalityCategory(m.modality).replaceFirstChar { it.uppercase() }
                                "${m.name} · $cat${if (cost.isNotEmpty()) " · $cost" else ""}"
                            } ?: d.modelId
                            InfoRow("Model", modelDisplay)
                            if (d.personality.isNotBlank()) InfoRow("Personality", d.personality)
                        }
                    }

                    if (d.children.isNotEmpty()) {
                        Spacer(Modifier.height(12.dp))
                        Card(modifier = Modifier.fillMaxWidth()) {
                            Column(modifier = Modifier.padding(16.dp)) {
                                Text("Direct Reports", style = MaterialTheme.typography.titleSmall)
                                d.children.filter { it.status != "fired" }.forEach { child ->
                                    TextButton(onClick = { nav.navigate("agent/${Uri.encode(host)}/${child.id}") }) {
                                        Text("${child.name} (${child.status})")
                                    }
                                }
                            }
                        }
                    }

                    if (d.skills.isNotEmpty()) {
                        Spacer(Modifier.height(12.dp))
                        Card(modifier = Modifier.fillMaxWidth()) {
                            Column(modifier = Modifier.padding(16.dp)) {
                                Text("Skills", style = MaterialTheme.typography.titleSmall)
                                d.skills.forEach { skill ->
                                    Text("• ${skill.name} (${skill.status})", style = MaterialTheme.typography.bodySmall, modifier = Modifier.padding(top = 4.dp))
                                }
                            }
                        }
                    }

                    Spacer(Modifier.height(16.dp))
                    Button(onClick = { showEditDialog = true }, modifier = Modifier.fillMaxWidth()) { Text("Edit Agent") }
                    Spacer(Modifier.height(8.dp))
                    Button(onClick = { showHireDialog = true }, modifier = Modifier.fillMaxWidth()) { Text("Hire Direct Report") }
                    if (!d.isCeo) {
                        Spacer(Modifier.height(8.dp))
                        OutlinedButton(onClick = { showFireDialog = true }, modifier = Modifier.fillMaxWidth()) { Text("Fire Agent") }
                    }
                }

                if (showFireDialog) {
                    AlertDialog(
                        onDismissRequest = { showFireDialog = false },
                        title = { Text("Fire ${d.name}?") },
                        text = { Text("This will fire the agent and all their direct reports. This cannot be undone.") },
                        confirmButton = {
                            Button(onClick = {
                                showFireDialog = false
                                scope.launch {
                                    try { client.fireAgent(agentId); nav.popBackStack() }
                                    catch (e: Exception) { error = e.message }
                                }
                            }) { Text("Fire") }
                        },
                        dismissButton = { TextButton(onClick = { showFireDialog = false }) { Text("Cancel") } },
                    )
                }

                if (showEditDialog) {
                    EditAgentDialog(
                        detail = d, models = models,
                        onDismiss = { showEditDialog = false },
                        onSave = { name, title, personality, modelId ->
                            scope.launch {
                                try { client.editAgent(agentId, name, title, personality, modelId); showEditDialog = false; load() }
                                catch (e: Exception) { error = e.message; showEditDialog = false }
                            }
                        },
                    )
                }

                if (showHireDialog) {
                    HireDirectReportDialog(
                        parentName = d.name, models = models, templates = templates,
                        onDismiss = { showHireDialog = false },
                        onHire = { name, title, personality, modelId ->
                            scope.launch {
                                try { client.hireAgent(agentId, name, title, personality, modelId); showHireDialog = false; load() }
                                catch (e: Exception) { error = e.message; showHireDialog = false }
                            }
                        },
                    )
                }
            }
        }
    }
}

@Composable
private fun ModelCategoryRow(selected: String, onSelect: (String) -> Unit) {
    Row(
        modifier = Modifier.horizontalScroll(rememberScrollState()),
        horizontalArrangement = Arrangement.spacedBy(6.dp),
    ) {
        MODEL_CATEGORIES.forEach { (id, label) ->
            FilterChip(selected = selected == id, onClick = { onSelect(id) }, label = { Text(label) })
        }
    }
}

@Composable
private fun EditAgentDialog(
    detail: AgentDetail,
    models: List<ModelItem>,
    onDismiss: () -> Unit,
    onSave: (name: String, title: String, personality: String, modelId: String) -> Unit,
) {
    var name by remember { mutableStateOf(detail.name) }
    var title by remember { mutableStateOf(detail.title) }
    var personality by remember { mutableStateOf(detail.personality) }
    var category by remember { mutableStateOf("all") }
    var selectedModel by remember { mutableStateOf(models.firstOrNull { it.id == detail.modelId }) }
    var modelExpanded by remember { mutableStateOf(false) }

    val filtered = models.filterByCategory(category)

    AlertDialog(
        onDismissRequest = onDismiss,
        title = { Text("Edit ${detail.name}") },
        text = {
            Column(modifier = Modifier.verticalScroll(rememberScrollState())) {
                OutlinedTextField(value = name, onValueChange = { name = it }, label = { Text("Name") }, singleLine = true, modifier = Modifier.fillMaxWidth())
                Spacer(Modifier.height(8.dp))
                OutlinedTextField(value = title, onValueChange = { title = it }, label = { Text("Title") }, singleLine = true, modifier = Modifier.fillMaxWidth())
                Spacer(Modifier.height(8.dp))
                OutlinedTextField(value = personality, onValueChange = { personality = it }, label = { Text("Personality") }, minLines = 2, modifier = Modifier.fillMaxWidth())
                Spacer(Modifier.height(10.dp))
                Text("Model", style = MaterialTheme.typography.labelMedium, color = MaterialTheme.colorScheme.onSurfaceVariant)
                Spacer(Modifier.height(4.dp))
                ModelCategoryRow(selected = category, onSelect = { category = it })
                Spacer(Modifier.height(6.dp))
                if (models.isNotEmpty()) {
                    ExposedDropdownMenuBox(expanded = modelExpanded, onExpandedChange = { modelExpanded = it }) {
                        OutlinedTextField(
                            value = selectedModel?.let { modelLabel(it) } ?: detail.modelId,
                            onValueChange = {},
                            readOnly = true,
                            label = { Text("${filtered.size} model${if (filtered.size != 1) "s" else ""} available") },
                            trailingIcon = { ExposedDropdownMenuDefaults.TrailingIcon(modelExpanded) },
                            modifier = Modifier.menuAnchor(MenuAnchorType.PrimaryNotEditable).fillMaxWidth(),
                        )
                        ExposedDropdownMenu(expanded = modelExpanded, onDismissRequest = { modelExpanded = false }) {
                            filtered.forEach { m ->
                                DropdownMenuItem(
                                    text = {
                                        Column {
                                            Text(m.name, style = MaterialTheme.typography.bodySmall)
                                            Text(modelMeta(m), style = MaterialTheme.typography.labelSmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
                                        }
                                    },
                                    onClick = { selectedModel = m; modelExpanded = false },
                                )
                            }
                        }
                    }
                }
            }
        },
        confirmButton = {
            Button(onClick = { onSave(name, title, personality, selectedModel?.id ?: detail.modelId) }, enabled = name.isNotBlank()) { Text("Save") }
        },
        dismissButton = { TextButton(onClick = onDismiss) { Text("Cancel") } },
    )
}

@Composable
private fun HireDirectReportDialog(
    parentName: String,
    models: List<ModelItem>,
    templates: List<AgentTemplateItem>,
    onDismiss: () -> Unit,
    onHire: (name: String, title: String, personality: String, modelId: String) -> Unit,
) {
    var name by remember { mutableStateOf("") }
    var title by remember { mutableStateOf("") }
    var personality by remember { mutableStateOf("") }
    var category by remember { mutableStateOf("all") }
    var selectedModel by remember { mutableStateOf(models.firstOrNull()) }
    var modelExpanded by remember { mutableStateOf(false) }
    var templateExpanded by remember { mutableStateOf(false) }

    val filtered = models.filterByCategory(category)

    AlertDialog(
        onDismissRequest = onDismiss,
        title = { Text("Hire — reports to $parentName") },
        text = {
            Column(modifier = Modifier.verticalScroll(rememberScrollState())) {
                if (templates.isNotEmpty()) {
                    Text("Load from Agent Shop template", style = MaterialTheme.typography.labelMedium, color = MaterialTheme.colorScheme.onSurfaceVariant)
                    Spacer(Modifier.height(4.dp))
                    ExposedDropdownMenuBox(expanded = templateExpanded, onExpandedChange = { templateExpanded = it }) {
                        OutlinedTextField(
                            value = if (name.isEmpty()) "Select a template (optional)" else "Template loaded — edit fields below",
                            onValueChange = {},
                            readOnly = true,
                            trailingIcon = { ExposedDropdownMenuDefaults.TrailingIcon(templateExpanded) },
                            modifier = Modifier.menuAnchor(MenuAnchorType.PrimaryNotEditable).fillMaxWidth(),
                        )
                        ExposedDropdownMenu(expanded = templateExpanded, onDismissRequest = { templateExpanded = false }) {
                            templates.forEach { t ->
                                DropdownMenuItem(
                                    text = {
                                        Column {
                                            Text(t.name, style = MaterialTheme.typography.bodySmall)
                                            Text(t.title, style = MaterialTheme.typography.labelSmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
                                        }
                                    },
                                    onClick = {
                                        name = t.name; title = t.title; personality = t.personality
                                        t.recommendedModelId?.let { mid -> selectedModel = models.firstOrNull { it.id == mid } ?: selectedModel }
                                        templateExpanded = false
                                    },
                                )
                            }
                        }
                    }
                    Spacer(Modifier.height(12.dp))
                }
                OutlinedTextField(value = name, onValueChange = { name = it }, label = { Text("Name") }, singleLine = true, modifier = Modifier.fillMaxWidth())
                Spacer(Modifier.height(8.dp))
                OutlinedTextField(value = title, onValueChange = { title = it }, label = { Text("Title") }, singleLine = true, modifier = Modifier.fillMaxWidth())
                Spacer(Modifier.height(8.dp))
                OutlinedTextField(value = personality, onValueChange = { personality = it }, label = { Text("Personality (optional)") }, minLines = 2, modifier = Modifier.fillMaxWidth())
                Spacer(Modifier.height(10.dp))
                Text("Model", style = MaterialTheme.typography.labelMedium, color = MaterialTheme.colorScheme.onSurfaceVariant)
                Spacer(Modifier.height(4.dp))
                ModelCategoryRow(selected = category, onSelect = { category = it })
                Spacer(Modifier.height(6.dp))
                if (models.isNotEmpty()) {
                    ExposedDropdownMenuBox(expanded = modelExpanded, onExpandedChange = { modelExpanded = it }) {
                        OutlinedTextField(
                            value = selectedModel?.let { modelLabel(it) } ?: "Select model",
                            onValueChange = {},
                            readOnly = true,
                            label = { Text("${filtered.size} model${if (filtered.size != 1) "s" else ""} available") },
                            trailingIcon = { ExposedDropdownMenuDefaults.TrailingIcon(modelExpanded) },
                            modifier = Modifier.menuAnchor(MenuAnchorType.PrimaryNotEditable).fillMaxWidth(),
                        )
                        ExposedDropdownMenu(expanded = modelExpanded, onDismissRequest = { modelExpanded = false }) {
                            filtered.forEach { m ->
                                DropdownMenuItem(
                                    text = {
                                        Column {
                                            Text(m.name, style = MaterialTheme.typography.bodySmall)
                                            Text(modelMeta(m), style = MaterialTheme.typography.labelSmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
                                        }
                                    },
                                    onClick = { selectedModel = m; modelExpanded = false },
                                )
                            }
                        }
                    }
                }
            }
        },
        confirmButton = {
            Button(
                onClick = { onHire(name, title, personality, selectedModel?.id ?: "") },
                enabled = name.isNotBlank() && title.isNotBlank() && selectedModel != null,
            ) { Text("Hire") }
        },
        dismissButton = { TextButton(onClick = onDismiss) { Text("Cancel") } },
    )
}

private fun modelLabel(m: ModelItem): String {
    val cost = m.pricingPrompt?.toDoubleOrNull()?.let { " · \$${fmtPrice(it * 1_000_000)}/1M in" } ?: if (m.isFree()) " · FREE" else ""
    return "${m.name}$cost"
}

private fun modelMeta(m: ModelItem): String {
    val parts = mutableListOf<String>()
    val cat = MODEL_CATEGORIES.firstOrNull { it.first == modalityCategory(m.modality) }?.second ?: "Text"
    parts.add(cat)
    if (m.isFree()) {
        parts.add("FREE")
    } else {
        m.pricingPrompt?.toDoubleOrNull()?.let { parts.add("In: \$${fmtPrice(it * 1_000_000)}/1M") }
        m.pricingCompletion?.toDoubleOrNull()?.let { parts.add("Out: \$${fmtPrice(it * 1_000_000)}/1M") }
    }
    if (m.supportsTools) parts.add("Tools ✓")
    return parts.joinToString(" · ")
}

private fun ModelItem.isFree() =
    (pricingPrompt?.toDoubleOrNull() ?: 1.0) == 0.0 && (pricingCompletion?.toDoubleOrNull() ?: 1.0) == 0.0

private fun fmtPrice(perMillion: Double) =
    if (perMillion < 1) "%.2f".format(perMillion) else "%.0f".format(perMillion)

@Composable
private fun InfoRow(label: String, value: String) {
    Row(modifier = Modifier.fillMaxWidth().padding(vertical = 3.dp), horizontalArrangement = Arrangement.SpaceBetween) {
        Text(label, style = MaterialTheme.typography.labelMedium, color = MaterialTheme.colorScheme.onSurfaceVariant)
        Text(value, style = MaterialTheme.typography.bodySmall)
    }
}
