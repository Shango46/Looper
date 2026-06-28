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
import com.looper.remote.data.CompanyInfo
import com.looper.remote.data.SkillItem
import com.looper.remote.ui.Session
import kotlinx.coroutines.launch

@Composable
fun SkillShopScreen(nav: NavHostController, host: String, companyId: Int) {
    val scope = rememberCoroutineScope()
    val company = Session.store.load().firstOrNull { it.host == host && it.companyId == companyId }
        ?: run { nav.popBackStack(); return }
    val client = Session.clientFor(company)

    var shopSkills by remember { mutableStateOf<List<SkillItem>?>(null) }
    var companyInfo by remember { mutableStateOf<CompanyInfo?>(null) }
    var error by remember { mutableStateOf<String?>(null) }
    var grantTarget by remember { mutableStateOf<SkillItem?>(null) }

    fun load() = scope.launch {
        try {
            shopSkills = client.listSkills().shop
            companyInfo = client.me()
            error = null
        } catch (e: Exception) { error = e.message }
    }

    LaunchedEffect(Unit) { load() }

    Scaffold(
        topBar = {
            TopAppBar(
                title = { Text("Skill Shop") },
                navigationIcon = { IconButton(onClick = { nav.popBackStack() }) { Icon(Icons.AutoMirrored.Filled.ArrowBack, "Back") } },
                actions = { IconButton(onClick = { load() }) { Icon(Icons.Filled.Refresh, "Refresh") } },
            )
        },
    ) { padding ->
        when {
            error != null -> Column(Modifier.fillMaxSize().padding(padding).padding(24.dp), verticalArrangement = Arrangement.Center) { Text("Error: $error") }
            shopSkills == null -> Box(Modifier.fillMaxSize().padding(padding), contentAlignment = Alignment.Center) { CircularProgressIndicator() }
            shopSkills!!.isEmpty() -> Column(Modifier.fillMaxSize().padding(padding).padding(24.dp), verticalArrangement = Arrangement.Center, horizontalAlignment = Alignment.CenterHorizontally) { Text("No skills in the shop yet.") }
            else -> LazyColumn(modifier = Modifier.fillMaxSize().padding(padding).padding(12.dp)) {
                items(shopSkills!!) { skill ->
                    Card(modifier = Modifier.fillMaxWidth().padding(vertical = 5.dp)) {
                        Column(modifier = Modifier.padding(14.dp)) {
                            Text(skill.name, style = MaterialTheme.typography.titleSmall)
                            if (skill.description.isNotBlank()) {
                                Spacer(Modifier.height(4.dp))
                                Text(skill.description.take(160), style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
                            }
                            if (skill.hasCustomTool) {
                                Text("Custom tool", style = MaterialTheme.typography.labelSmall, color = MaterialTheme.colorScheme.tertiary)
                            }
                            Spacer(Modifier.height(8.dp))
                            Button(onClick = { grantTarget = skill }, modifier = Modifier.fillMaxWidth()) {
                                Text("Grant to agent")
                            }
                        }
                    }
                }
            }
        }
    }

    grantTarget?.let { skill ->
        GrantSkillDialog(
            skill = skill,
            orgTree = companyInfo?.orgTree,
            onDismiss = { grantTarget = null },
            onGrant = { agentId ->
                scope.launch {
                    try { client.grantSkill(skill.id, agentId); grantTarget = null }
                    catch (e: Exception) { error = e.message; grantTarget = null }
                }
            },
        )
    }
}

@Composable
private fun GrantSkillDialog(
    skill: SkillItem,
    orgTree: AgentNode?,
    onDismiss: () -> Unit,
    onGrant: (agentId: Int) -> Unit,
) {
    fun flatten(node: AgentNode?): List<AgentNode> {
        if (node == null) return emptyList()
        return listOf(node) + node.children.filter { it.status == "active" }.flatMap { flatten(it) }
    }
    val agents = flatten(orgTree)
    var selected by remember { mutableStateOf(agents.firstOrNull()) }
    var expanded by remember { mutableStateOf(false) }

    AlertDialog(
        onDismissRequest = onDismiss,
        title = { Text("Grant — ${skill.name}") },
        text = {
            Column {
                Text("Select an agent to grant this skill to:", style = MaterialTheme.typography.bodyMedium)
                Spacer(Modifier.height(8.dp))
                if (agents.isNotEmpty()) {
                    ExposedDropdownMenuBox(expanded = expanded, onExpandedChange = { expanded = it }) {
                        OutlinedTextField(
                            value = selected?.name ?: "Select agent",
                            onValueChange = {},
                            readOnly = true,
                            label = { Text("Agent") },
                            trailingIcon = { ExposedDropdownMenuDefaults.TrailingIcon(expanded) },
                            modifier = Modifier.menuAnchor(MenuAnchorType.PrimaryNotEditable).fillMaxWidth(),
                        )
                        ExposedDropdownMenu(expanded = expanded, onDismissRequest = { expanded = false }) {
                            agents.forEach { agent ->
                                DropdownMenuItem(
                                    text = { Text("${agent.name} — ${agent.title}") },
                                    onClick = { selected = agent; expanded = false },
                                )
                            }
                        }
                    }
                } else {
                    Text("No agents found.", style = MaterialTheme.typography.bodySmall)
                }
            }
        },
        confirmButton = {
            Button(onClick = { selected?.let { onGrant(it.id) } }, enabled = selected != null) {
                Text("Grant")
            }
        },
        dismissButton = { TextButton(onClick = onDismiss) { Text("Cancel") } },
    )
}
