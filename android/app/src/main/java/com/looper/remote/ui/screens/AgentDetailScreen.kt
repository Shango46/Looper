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
import androidx.compose.material3.DropdownMenu
import androidx.compose.material3.DropdownMenuItem
import androidx.compose.material3.ExposedDropdownMenuBox
import androidx.compose.material3.ExposedDropdownMenuDefaults
import androidx.compose.material3.MenuAnchorType
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
import com.looper.remote.data.AgentDetail
import com.looper.remote.data.ApiException
import com.looper.remote.data.ModelInfo
import com.looper.remote.data.SavedCompany
import com.looper.remote.ui.Session
import kotlinx.coroutines.launch

@Composable
fun AgentDetailScreen(nav: NavHostController, host: String, companyId: Int, agentId: Int) {
    val company = Session.store.load().firstOrNull { it.host == host && it.companyId == companyId } ?: run {
        Text("Company not found.")
        return
    }
    var agent by remember { mutableStateOf<AgentDetail?>(null) }
    var error by remember { mutableStateOf<String?>(null) }
    var editing by remember { mutableStateOf(false) }
    var hiring by remember { mutableStateOf(false) }
    val scope = rememberCoroutineScope()

    suspend fun refresh() {
        try {
            agent = Session.clientFor(company).getAgent(agentId)
        } catch (e: ApiException) {
            if (Session.needsReconnect(e)) nav.navigate("reconnect/$host/$companyId") { popUpTo("switcher") }
            else error = e.message
        } catch (e: Exception) {
            error = "Could not reach $host."
        }
    }

    LaunchedEffect(agentId) { refresh() }

    Scaffold(topBar = { TopAppBar(title = { Text(agent?.name ?: "Agent") }) }) { padding ->
        Column(modifier = Modifier.fillMaxSize().padding(padding).padding(16.dp)) {
            agent?.let { a ->
                Text("${a.title} · ${a.status}${if (a.is_ceo) " · CEO" else ""}", style = MaterialTheme.typography.bodyMedium)
                Text("Model: ${a.model_id ?: "none"}", style = MaterialTheme.typography.bodySmall)
                Text(a.personality, style = MaterialTheme.typography.bodySmall, modifier = Modifier.padding(top = 8.dp))

                Row(modifier = Modifier.fillMaxWidth().padding(top = 12.dp)) {
                    Button(onClick = { nav.navigate("chat/$host/$companyId/$agentId") }) { Text("Chat") }
                }

                if (a.status != "fired") {
                    Button(onClick = { editing = !editing }, modifier = Modifier.padding(top = 8.dp)) {
                        Text(if (editing) "Cancel edit" else "Edit")
                    }
                    if (editing) {
                        EditAgentForm(company, a) { name, title, personality, modelId ->
                            scope.launch {
                                try {
                                    Session.clientFor(company).editAgent(agentId, name, title, personality, modelId)
                                    editing = false
                                    refresh()
                                } catch (e: Exception) { error = e.message }
                            }
                        }
                    }

                    Button(
                        onClick = {
                            scope.launch {
                                try { Session.clientFor(company).fireAgent(agentId); refresh() } catch (e: Exception) { error = e.message }
                            }
                        },
                        modifier = Modifier.padding(top = 8.dp),
                    ) { Text("Fire") }

                    Button(onClick = { hiring = !hiring }, modifier = Modifier.padding(top = 8.dp)) {
                        Text(if (hiring) "Cancel hire" else "Hire under this agent")
                    }
                    if (hiring) {
                        HireForm(company) { name, title, personality, modelId ->
                            scope.launch {
                                try {
                                    Session.clientFor(company).hireAgent(agentId, name, title, personality, modelId)
                                    hiring = false
                                    refresh()
                                } catch (e: Exception) { error = e.message }
                            }
                        }
                    }
                } else {
                    Text("This agent has been fired.", color = Color.Red, modifier = Modifier.padding(top = 8.dp))
                    ReplaceForm(company, a) { name, title, personality, modelId ->
                        scope.launch {
                            try {
                                Session.clientFor(company).replaceAgent(agentId, name, title, personality, modelId)
                                refresh()
                            } catch (e: Exception) { error = e.message }
                        }
                    }
                }

                Text("Skills", style = MaterialTheme.typography.titleMedium, modifier = Modifier.padding(top = 16.dp))
                LazyColumn { items(a.skills) { s -> Text("${s.name} — ${s.status}") } }
            }
            error?.let { Text(it, color = Color.Red, modifier = Modifier.padding(top = 8.dp)) }
        }
    }
}

@Composable
private fun EditAgentForm(company: SavedCompany, agent: AgentDetail, onSave: (String, String, String, String) -> Unit) {
    var name by remember { mutableStateOf(agent.name) }
    var title by remember { mutableStateOf(agent.title) }
    var personality by remember { mutableStateOf(agent.personality) }
    var modelId by remember { mutableStateOf(agent.model_id ?: "") }
    AgentFieldsForm(company, name, { name = it }, title, { title = it }, personality, { personality = it }, modelId, { modelId = it }, "Save") {
        onSave(name, title, personality, modelId)
    }
}

@Composable
private fun HireForm(company: SavedCompany, onHire: (String, String, String, String) -> Unit) {
    var name by remember { mutableStateOf("") }
    var title by remember { mutableStateOf("") }
    var personality by remember { mutableStateOf("") }
    var modelId by remember { mutableStateOf("") }
    AgentFieldsForm(company, name, { name = it }, title, { title = it }, personality, { personality = it }, modelId, { modelId = it }, "Hire") {
        onHire(name, title, personality, modelId)
    }
}

@Composable
private fun ReplaceForm(company: SavedCompany, fired: AgentDetail, onReplace: (String, String, String, String) -> Unit) {
    var name by remember { mutableStateOf("") }
    var title by remember { mutableStateOf(fired.title) }
    var personality by remember { mutableStateOf("") }
    var modelId by remember { mutableStateOf(fired.model_id ?: "") }
    Text("Replace with a new agent", style = MaterialTheme.typography.titleSmall, modifier = Modifier.padding(top = 12.dp))
    AgentFieldsForm(company, name, { name = it }, title, { title = it }, personality, { personality = it }, modelId, { modelId = it }, "Replace") {
        onReplace(name, title, personality, modelId)
    }
}

@Composable
private fun AgentFieldsForm(
    company: SavedCompany,
    name: String, onName: (String) -> Unit,
    title: String, onTitle: (String) -> Unit,
    personality: String, onPersonality: (String) -> Unit,
    modelId: String, onModelId: (String) -> Unit,
    buttonLabel: String,
    onSubmit: () -> Unit,
) {
    var models by remember { mutableStateOf<List<ModelInfo>>(emptyList()) }
    LaunchedEffect(company) {
        try { models = Session.clientFor(company).listModels().filter { it.supports_tools } } catch (e: Exception) { /* picker stays empty, user can retry by reopening the form */ }
    }

    OutlinedTextField(name, onName, label = { Text("Name") }, modifier = Modifier.fillMaxWidth().padding(top = 8.dp))
    OutlinedTextField(title, onTitle, label = { Text("Title") }, modifier = Modifier.fillMaxWidth().padding(top = 8.dp))
    OutlinedTextField(personality, onPersonality, label = { Text("Personality") }, modifier = Modifier.fillMaxWidth().padding(top = 8.dp))

    var expanded by remember { mutableStateOf(false) }
    ExposedDropdownMenuBox(expanded = expanded, onExpandedChange = { expanded = it }, modifier = Modifier.padding(top = 8.dp)) {
        OutlinedTextField(
            value = modelId,
            onValueChange = onModelId,
            readOnly = false,
            label = { Text("Model (tool-capable models shown)") },
            trailingIcon = { ExposedDropdownMenuDefaults.TrailingIcon(expanded = expanded) },
            modifier = Modifier.fillMaxWidth().menuAnchor(MenuAnchorType.PrimaryEditable, true),
        )
        DropdownMenu(expanded = expanded && models.isNotEmpty(), onDismissRequest = { expanded = false }) {
            models.forEach { m ->
                DropdownMenuItem(text = { Text(m.name) }, onClick = { onModelId(m.id); expanded = false })
            }
        }
    }

    Button(
        enabled = name.isNotBlank() && title.isNotBlank() && modelId.isNotBlank(),
        onClick = onSubmit,
        modifier = Modifier.fillMaxWidth().padding(top = 8.dp),
    ) { Text(buttonLabel) }
}
