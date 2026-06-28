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
import com.looper.remote.data.ApprovalItem
import com.looper.remote.ui.Session
import kotlinx.coroutines.launch

@Composable
fun ApprovalsScreen(nav: NavHostController, host: String, companyId: Int) {
    val company = Session.store.load().firstOrNull { it.host == host && it.companyId == companyId } ?: run {
        Text("Company not found.")
        return
    }
    var approvals by remember { mutableStateOf<List<ApprovalItem>>(emptyList()) }
    var error by remember { mutableStateOf<String?>(null) }
    val scope = rememberCoroutineScope()

    suspend fun refresh() {
        try {
            approvals = Session.clientFor(company).listApprovals()
        } catch (e: ApiException) {
            if (Session.needsReconnect(e)) nav.navigate("reconnect/$host/$companyId") { popUpTo("switcher") }
            else error = e.message
        } catch (e: Exception) {
            error = "Could not reach $host."
        }
    }

    LaunchedEffect(Unit) { refresh() }

    Scaffold(topBar = { TopAppBar(title = { Text("Approvals") }) }) { padding ->
        Column(modifier = Modifier.fillMaxSize().padding(padding).padding(12.dp)) {
            error?.let { Text(it, color = Color.Red) }
            if (approvals.isEmpty()) {
                Text("Nothing pending.", style = MaterialTheme.typography.bodyMedium)
            }
            LazyColumn(modifier = Modifier.fillMaxSize()) {
                items(approvals) { a ->
                    Card(modifier = Modifier.fillMaxWidth().padding(vertical = 4.dp)) {
                        Column(modifier = Modifier.padding(12.dp)) {
                            Text(
                                if (a.kind == "skill_grant") "Skill grant request" else "Risky action",
                                style = MaterialTheme.typography.titleSmall,
                            )
                            Text(a.payload.toString(), style = MaterialTheme.typography.bodySmall)
                            Row(modifier = Modifier.padding(top = 8.dp)) {
                                Button(onClick = {
                                    scope.launch {
                                        try { Session.clientFor(company).approveApproval(a.id); refresh() } catch (e: Exception) { error = e.message }
                                    }
                                }) { Text("Approve") }
                                Button(
                                    onClick = {
                                        scope.launch {
                                            try { Session.clientFor(company).denyApproval(a.id); refresh() } catch (e: Exception) { error = e.message }
                                        }
                                    },
                                    modifier = Modifier.padding(start = 8.dp),
                                ) { Text("Deny") }
                            }
                        }
                    }
                }
            }
        }
    }
}
