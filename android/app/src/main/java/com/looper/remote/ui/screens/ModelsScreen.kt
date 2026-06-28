@file:OptIn(androidx.compose.material3.ExperimentalMaterial3Api::class)

package com.looper.remote.ui.screens

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
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.rememberScrollState
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.ArrowBack
import androidx.compose.material.icons.filled.Refresh
import androidx.compose.material3.Card
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.FilterChip
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
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
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp
import androidx.navigation.NavHostController
import com.looper.remote.data.ModelItem
import com.looper.remote.ui.MODEL_CATEGORIES
import com.looper.remote.ui.Session
import com.looper.remote.ui.filterByCategory
import com.looper.remote.ui.modalityCategory
import kotlinx.coroutines.launch

@Composable
fun ModelsScreen(nav: NavHostController, host: String, companyId: Int) {
    val scope = rememberCoroutineScope()
    val company = Session.store.load().firstOrNull { it.host == host && it.companyId == companyId }
        ?: run { nav.popBackStack(); return }

    var allModels by remember { mutableStateOf<List<ModelItem>?>(null) }
    var error by remember { mutableStateOf<String?>(null) }
    var search by remember { mutableStateOf("") }
    var category by remember { mutableStateOf("all") }

    fun load() = scope.launch {
        try { allModels = Session.clientFor(company).listModels(); error = null }
        catch (e: Exception) { error = e.message }
    }

    LaunchedEffect(Unit) { load() }

    val filtered = allModels
        ?.filterByCategory(category)
        ?.filter { m -> search.isBlank() || m.name.contains(search, ignoreCase = true) || m.id.contains(search, ignoreCase = true) }
        ?: emptyList()

    Scaffold(
        topBar = {
            TopAppBar(
                title = { Text("Models") },
                navigationIcon = { IconButton(onClick = { nav.popBackStack() }) { Icon(Icons.AutoMirrored.Filled.ArrowBack, "Back") } },
                actions = { IconButton(onClick = { load() }) { Icon(Icons.Filled.Refresh, "Refresh") } },
            )
        },
    ) { padding ->
        when {
            error != null -> Column(Modifier.fillMaxSize().padding(padding).padding(24.dp), verticalArrangement = Arrangement.Center) { Text("Error: $error") }
            allModels == null -> Box(Modifier.fillMaxSize().padding(padding), contentAlignment = Alignment.Center) { CircularProgressIndicator() }
            else -> Column(modifier = Modifier.fillMaxSize().padding(padding)) {
                Column(modifier = Modifier.padding(horizontal = 12.dp, vertical = 6.dp)) {
                    OutlinedTextField(
                        value = search,
                        onValueChange = { search = it },
                        placeholder = { Text("Search models…") },
                        singleLine = true,
                        modifier = Modifier.fillMaxWidth(),
                    )
                    Spacer(Modifier.height(6.dp))
                    Row(
                        modifier = Modifier.horizontalScroll(rememberScrollState()),
                        horizontalArrangement = Arrangement.spacedBy(6.dp),
                    ) {
                        MODEL_CATEGORIES.forEach { (id, label) ->
                            FilterChip(
                                selected = category == id,
                                onClick = { category = id },
                                label = { Text(label) },
                            )
                        }
                    }
                    Spacer(Modifier.height(4.dp))
                    Text(
                        "${filtered.size} of ${allModels!!.size} models",
                        style = MaterialTheme.typography.labelSmall,
                        color = MaterialTheme.colorScheme.onSurfaceVariant,
                    )
                }
                LazyColumn(modifier = Modifier.fillMaxSize().padding(horizontal = 12.dp)) {
                    items(filtered) { model ->
                        ModelCard(model)
                    }
                }
            }
        }
    }
}

@Composable
private fun ModelCard(model: ModelItem) {
    val cat = MODEL_CATEGORIES.firstOrNull { it.first == modalityCategory(model.modality) }?.second ?: "Text"
    val isFree = (model.pricingPrompt?.toDoubleOrNull() ?: 1.0) == 0.0 &&
                 (model.pricingCompletion?.toDoubleOrNull() ?: 1.0) == 0.0

    Card(modifier = Modifier.fillMaxWidth().padding(vertical = 3.dp)) {
        Column(modifier = Modifier.padding(12.dp)) {
            Row(modifier = Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.SpaceBetween, verticalAlignment = Alignment.Top) {
                Column(modifier = Modifier.weight(1f)) {
                    Text(model.name, style = MaterialTheme.typography.bodyMedium)
                    Text(model.id, style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
                }
                Column(horizontalAlignment = Alignment.End) {
                    Text(cat, style = MaterialTheme.typography.labelSmall, color = MaterialTheme.colorScheme.tertiary)
                    if (model.supportsTools) Text("Tools ✓", style = MaterialTheme.typography.labelSmall, color = MaterialTheme.colorScheme.primary)
                }
            }
            Spacer(Modifier.height(4.dp))
            Row(horizontalArrangement = Arrangement.spacedBy(12.dp)) {
                model.contextLength?.let { Text(fmtCtx(it) + " ctx", style = MaterialTheme.typography.labelSmall, color = MaterialTheme.colorScheme.onSurfaceVariant) }
                if (isFree) {
                    Text("FREE", style = MaterialTheme.typography.labelSmall, color = MaterialTheme.colorScheme.primary)
                } else {
                    model.pricingPrompt?.toDoubleOrNull()?.let { Text("In: \$${fmtPrice(it * 1_000_000)}/1M", style = MaterialTheme.typography.labelSmall, color = MaterialTheme.colorScheme.onSurfaceVariant) }
                    model.pricingCompletion?.toDoubleOrNull()?.let { Text("Out: \$${fmtPrice(it * 1_000_000)}/1M", style = MaterialTheme.typography.labelSmall, color = MaterialTheme.colorScheme.onSurfaceVariant) }
                }
            }
        }
    }
}

private fun fmtPrice(perMillion: Double) =
    if (perMillion < 1) "%.2f".format(perMillion) else "%.0f".format(perMillion)

private fun fmtCtx(tokens: Int) = when {
    tokens >= 1_000_000 -> "${"%.0f".format(tokens / 1_000_000.0)}M"
    tokens >= 1_000 -> "${"%.0f".format(tokens / 1_000.0)}K"
    else -> "$tokens"
}
