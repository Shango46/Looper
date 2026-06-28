@file:OptIn(androidx.compose.material3.ExperimentalMaterial3Api::class)

package com.looper.remote.ui.screens

import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Add
import androidx.compose.material.icons.filled.Delete
import androidx.compose.material3.Card
import androidx.compose.material3.FloatingActionButton
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Text
import androidx.compose.material3.TopAppBar
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateMapOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.unit.dp
import androidx.navigation.NavHostController
import com.looper.remote.data.SavedCompaniesStore
import com.looper.remote.ui.Session
import kotlinx.coroutines.launch

@Composable
fun SwitcherScreen(nav: NavHostController) {
    val context = LocalContext.current
    var companies by remember { mutableStateOf(Session.store.load()) }
    // null = checking, true = reachable, false = unreachable — keyed by host::companyId.
    val reachability = remember { mutableStateMapOf<String, Boolean?>() }

    LaunchedEffect(companies) {
        for (company in companies) {
            val key = SavedCompaniesStore.keyFor(company)
            reachability[key] = null
            launch {
                reachability[key] = try {
                    Session.clientFor(company).me()
                    true
                } catch (e: Exception) {
                    false
                }
            }
        }
    }

    Scaffold(
        topBar = { TopAppBar(title = { Text("Looper Remote") }) },
        floatingActionButton = {
            FloatingActionButton(onClick = { nav.navigate("add") }) {
                Icon(Icons.Filled.Add, contentDescription = "Add company")
            }
        },
    ) { padding ->
        if (companies.isEmpty()) {
            Column(
                modifier = Modifier.fillMaxSize().padding(padding).padding(24.dp),
                verticalArrangement = Arrangement.Center,
            ) {
                Text("No companies added yet. Tap + to connect to one using its host and code from the Looper PC app.")
            }
        } else {
            LazyColumn(modifier = Modifier.fillMaxSize().padding(padding).padding(12.dp)) {
                items(companies) { company ->
                    Card(modifier = Modifier.fillMaxWidth().padding(vertical = 6.dp)) {
                        Row(
                            modifier = Modifier.fillMaxWidth().padding(16.dp),
                            verticalAlignment = Alignment.CenterVertically,
                            horizontalArrangement = Arrangement.SpaceBetween,
                        ) {
                            Row(
                                modifier = Modifier
                                    .weight(1f)
                                    .clickable { nav.navigate("home/${company.host}/${company.companyId}") },
                                verticalAlignment = Alignment.CenterVertically,
                            ) {
                                val state = reachability[SavedCompaniesStore.keyFor(company)]
                                val dotColor = when (state) {
                                    true -> Color(0xFF4CAF50)
                                    false -> Color(0xFFE53935)
                                    null -> Color(0xFF9E9E9E)
                                }
                                Box(
                                    modifier = Modifier.size(10.dp).clip(CircleShape).background(dotColor),
                                )
                                Column(modifier = Modifier.padding(start = 10.dp)) {
                                    Text(company.companyName, style = MaterialTheme.typography.titleMedium)
                                    Text(company.host, style = MaterialTheme.typography.bodySmall)
                                }
                            }
                            IconButton(onClick = {
                                Session.forget(company)
                                companies = Session.store.load()
                                Session.syncPollingService(context)
                            }) {
                                Icon(Icons.Filled.Delete, contentDescription = "Remove")
                            }
                        }
                    }
                }
            }
        }
    }
}
