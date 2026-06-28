@file:OptIn(androidx.compose.material3.ExperimentalMaterial3Api::class)

package com.looper.remote.ui.screens

import androidx.compose.foundation.layout.Column
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
import com.looper.remote.data.SkillSummary
import com.looper.remote.ui.Session
import kotlinx.coroutines.launch

@Composable
fun SkillsScreen(nav: NavHostController, host: String, companyId: Int) {
    val company = Session.store.load().firstOrNull { it.host == host && it.companyId == companyId } ?: run {
        Text("Company not found.")
        return
    }
    var own by remember { mutableStateOf<List<SkillSummary>>(emptyList()) }
    var shop by remember { mutableStateOf<List<SkillSummary>>(emptyList()) }
    var error by remember { mutableStateOf<String?>(null) }
    var creating by remember { mutableStateOf(false) }
    val scope = rememberCoroutineScope()

    suspend fun refresh() {
        try {
            val resp = Session.clientFor(company).listSkills()
            own = resp.own
            shop = resp.shop
        } catch (e: ApiException) {
            if (Session.needsReconnect(e)) nav.navigate("reconnect/$host/$companyId") { popUpTo("switcher") }
            else error = e.message
        } catch (e: Exception) {
            error = "Could not reach $host."
        }
    }

    LaunchedEffect(Unit) { refresh() }

    Scaffold(topBar = { TopAppBar(title = { Text("Skills") }) }) { padding ->
        Column(modifier = Modifier.fillMaxSize().padding(padding).padding(12.dp)) {
            error?.let { Text(it, color = Color.Red) }

            Button(onClick = { creating = !creating }) { Text(if (creating) "Cancel" else "Create new skill") }
            if (creating) {
                CreateSkillForm(onCreate = { agentId, name, description, instructions, visibility ->
                    scope.launch {
                        try {
                            Session.clientFor(company).createSkill(agentId, name, description, instructions, visibility)
                            creating = false
                            refresh()
                        } catch (e: Exception) { error = e.message }
                    }
                })
            }

            Text("Owned by this company", style = MaterialTheme.typography.titleMedium, modifier = Modifier.padding(top = 16.dp))
            LazyColumn(modifier = Modifier.fillMaxWidth()) {
                items(own) { s -> SkillRow(s) }
            }

            Text("Skill Shop", style = MaterialTheme.typography.titleMedium, modifier = Modifier.padding(top = 16.dp))
            LazyColumn(modifier = Modifier.fillMaxSize()) {
                items(shop) { s ->
                    SkillRow(s) {
                        GrantRow(onGrant = { agentId ->
                            scope.launch {
                                try { Session.clientFor(company).grantSkill(s.id, agentId) } catch (e: Exception) { error = e.message }
                            }
                        })
                    }
                }
            }
        }
    }
}

@Composable
private fun SkillRow(s: SkillSummary, extra: (@Composable () -> Unit)? = null) {
    Card(modifier = Modifier.fillMaxWidth().padding(vertical = 4.dp)) {
        Column(modifier = Modifier.padding(12.dp)) {
            Text("${s.name} (${s.visibility})", style = MaterialTheme.typography.bodyLarge)
            Text(s.description, style = MaterialTheme.typography.bodySmall)
            extra?.invoke()
        }
    }
}

@Composable
private fun GrantRow(onGrant: (Int) -> Unit) {
    var agentIdText by remember { mutableStateOf("") }
    OutlinedTextField(
        value = agentIdText,
        onValueChange = { agentIdText = it.filter { c -> c.isDigit() } },
        label = { Text("Agent ID to grant to") },
        modifier = Modifier.fillMaxWidth().padding(top = 4.dp),
    )
    Button(
        enabled = agentIdText.isNotBlank(),
        onClick = { agentIdText.toIntOrNull()?.let(onGrant) },
        modifier = Modifier.padding(top = 4.dp),
    ) { Text("Grant") }
}

@Composable
private fun CreateSkillForm(onCreate: (Int, String, String, String, String) -> Unit) {
    var agentIdText by remember { mutableStateOf("") }
    var name by remember { mutableStateOf("") }
    var description by remember { mutableStateOf("") }
    var instructions by remember { mutableStateOf("") }
    var visibility by remember { mutableStateOf("private") }

    OutlinedTextField(agentIdText, { agentIdText = it.filter { c -> c.isDigit() } }, label = { Text("Owner agent ID") }, modifier = Modifier.fillMaxWidth().padding(top = 8.dp))
    OutlinedTextField(name, { name = it }, label = { Text("Name") }, modifier = Modifier.fillMaxWidth().padding(top = 8.dp))
    OutlinedTextField(description, { description = it }, label = { Text("Description") }, modifier = Modifier.fillMaxWidth().padding(top = 8.dp))
    OutlinedTextField(instructions, { instructions = it }, label = { Text("Instructions") }, modifier = Modifier.fillMaxWidth().padding(top = 8.dp))
    OutlinedTextField(visibility, { visibility = it }, label = { Text("Visibility (private/company/shop)") }, modifier = Modifier.fillMaxWidth().padding(top = 8.dp))
    Button(
        enabled = agentIdText.isNotBlank() && name.isNotBlank(),
        onClick = { agentIdText.toIntOrNull()?.let { onCreate(it, name, description, instructions, visibility) } },
        modifier = Modifier.fillMaxWidth().padding(top = 8.dp),
    ) { Text("Create") }
}
