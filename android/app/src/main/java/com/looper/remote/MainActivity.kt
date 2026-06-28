@file:OptIn(androidx.compose.material3.ExperimentalMaterial3Api::class)

package com.looper.remote

import android.Manifest
import android.content.Intent
import android.content.pm.PackageManager
import android.os.Build
import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Surface
import androidx.compose.material3.darkColorScheme
import androidx.compose.material3.lightColorScheme
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import androidx.core.content.ContextCompat
import androidx.navigation.NavHostController
import androidx.navigation.NavType
import androidx.navigation.compose.NavHost
import androidx.navigation.compose.composable
import androidx.navigation.compose.rememberNavController
import androidx.navigation.navArgument
import com.looper.remote.ui.Session
import com.looper.remote.ui.screens.AddCompanyScreen
import com.looper.remote.ui.screens.AgentChatScreen
import com.looper.remote.ui.screens.AgentDetailScreen
import com.looper.remote.ui.screens.AgentShopScreen
import com.looper.remote.ui.screens.ApprovalsScreen
import com.looper.remote.ui.screens.CompanyActivityScreen
import com.looper.remote.ui.screens.CompanyHomeScreen
import com.looper.remote.ui.screens.FileBrowserScreen
import com.looper.remote.ui.screens.McpServersScreen
import com.looper.remote.ui.screens.ModelsScreen
import com.looper.remote.ui.screens.ReconnectScreen
import com.looper.remote.ui.screens.SkillShopScreen
import com.looper.remote.ui.screens.SettingsScreen
import com.looper.remote.ui.screens.SkillsScreen
import com.looper.remote.ui.screens.SwitcherScreen
import com.looper.remote.ui.screens.TailscaleGateScreen
import android.net.Uri
import kotlinx.coroutines.delay

data class DeepLinkTarget(val host: String, val companyId: Int)

class MainActivity : ComponentActivity() {
    private val notificationPermissionLauncher =
        registerForActivityResult(ActivityResultContracts.RequestPermission()) {
            Session.syncPollingService(this)
        }

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        Session.init(this)
        AppTheme.isDark.value = ServerPrefs(this).darkMode
        requestNotificationPermissionThenSync()

        setContent {
            val isDark by AppTheme.isDark
            MaterialTheme(colorScheme = if (isDark) darkColorScheme() else lightColorScheme()) {
                Surface(modifier = Modifier) {
                    LooperRemoteApp(deepLinkFromIntent(intent))
                }
            }
        }
    }

    override fun onResume() {
        super.onResume()
        if (Build.VERSION.SDK_INT < Build.VERSION_CODES.TIRAMISU ||
            ContextCompat.checkSelfPermission(this, Manifest.permission.POST_NOTIFICATIONS) == PackageManager.PERMISSION_GRANTED
        ) {
            Session.syncPollingService(this)
        }
    }

    override fun onNewIntent(intent: Intent) {
        super.onNewIntent(intent)
        setIntent(intent)
        setContent {
            val isDark by AppTheme.isDark
            MaterialTheme(colorScheme = if (isDark) darkColorScheme() else lightColorScheme()) {
                Surface(modifier = Modifier) {
                    LooperRemoteApp(deepLinkFromIntent(intent))
                }
            }
        }
    }

    private fun deepLinkFromIntent(intent: Intent?): DeepLinkTarget? {
        val host = intent?.getStringExtra("deeplink_host") ?: return null
        val companyId = intent.getIntExtra("deeplink_company_id", -1)
        if (companyId < 0) return null
        return DeepLinkTarget(host, companyId)
    }

    private fun requestNotificationPermissionThenSync() {
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.TIRAMISU) {
            val granted = ContextCompat.checkSelfPermission(this, Manifest.permission.POST_NOTIFICATIONS) == PackageManager.PERMISSION_GRANTED
            if (granted) Session.syncPollingService(this)
            else notificationPermissionLauncher.launch(Manifest.permission.POST_NOTIFICATIONS)
        } else {
            Session.syncPollingService(this)
        }
    }
}

@Composable
fun LooperRemoteApp(deepLink: DeepLinkTarget? = null) {
    var tailscaleActive by remember { mutableStateOf(TailscaleDetector.isActive()) }

    // Check for APK update in background
    LaunchedEffect(Unit) {
        delay(5_000)
        // UpdateChecker runs passively; future: show a snackbar in SwitcherScreen
    }

    if (!tailscaleActive) {
        TailscaleGateScreen(onRefresh = { tailscaleActive = TailscaleDetector.isActive() })
        return
    }

    LooperRemoteNavHost(deepLink)
}

@Composable
fun LooperRemoteNavHost(deepLink: DeepLinkTarget? = null) {
    val navController: NavHostController = rememberNavController()
    var consumedDeepLink by remember { mutableStateOf(false) }

    LaunchedEffect(deepLink) {
        if (deepLink != null && !consumedDeepLink) {
            consumedDeepLink = true
            navController.navigate("approvals/${Uri.encode(deepLink.host)}/${deepLink.companyId}")
        }
    }

    NavHost(navController = navController, startDestination = "switcher") {
        composable("switcher") { SwitcherScreen(navController) }
        composable("add") { AddCompanyScreen(navController) }
        composable(
            "reconnect/{host}/{companyId}",
            arguments = listOf(navArgument("companyId") { type = NavType.IntType }),
        ) {
            ReconnectScreen(navController, it.arguments!!.getString("host")!!, it.arguments!!.getInt("companyId"))
        }
        composable(
            "home/{host}/{companyId}",
            arguments = listOf(navArgument("companyId") { type = NavType.IntType }),
        ) {
            CompanyHomeScreen(navController, it.arguments!!.getString("host")!!, it.arguments!!.getInt("companyId"))
        }
        composable(
            "agent/{host}/{agentId}",
            arguments = listOf(navArgument("agentId") { type = NavType.IntType }),
        ) {
            AgentDetailScreen(navController, it.arguments!!.getString("host")!!, it.arguments!!.getInt("agentId"))
        }
        composable(
            "chat/{host}/{agentId}",
            arguments = listOf(navArgument("agentId") { type = NavType.IntType }),
        ) {
            AgentChatScreen(navController, it.arguments!!.getString("host")!!, it.arguments!!.getInt("agentId"))
        }
        composable(
            "activity/{host}/{companyId}",
            arguments = listOf(navArgument("companyId") { type = NavType.IntType }),
        ) {
            CompanyActivityScreen(navController, it.arguments!!.getString("host")!!, it.arguments!!.getInt("companyId"))
        }
        composable(
            "approvals/{host}/{companyId}",
            arguments = listOf(navArgument("companyId") { type = NavType.IntType }),
        ) {
            ApprovalsScreen(navController, it.arguments!!.getString("host")!!, it.arguments!!.getInt("companyId"))
        }
        composable(
            "skills/{host}/{companyId}",
            arguments = listOf(navArgument("companyId") { type = NavType.IntType }),
        ) {
            SkillsScreen(navController, it.arguments!!.getString("host")!!, it.arguments!!.getInt("companyId"))
        }
        composable(
            "files/{host}/{companyId}",
            arguments = listOf(navArgument("companyId") { type = NavType.IntType }),
        ) {
            FileBrowserScreen(navController, it.arguments!!.getString("host")!!, it.arguments!!.getInt("companyId"))
        }
        composable(
            "mcp/{host}/{companyId}",
            arguments = listOf(navArgument("companyId") { type = NavType.IntType }),
        ) {
            McpServersScreen(navController, it.arguments!!.getString("host")!!, it.arguments!!.getInt("companyId"))
        }
        // New screens
        composable(
            "agent_shop/{host}/{companyId}",
            arguments = listOf(navArgument("companyId") { type = NavType.IntType }),
        ) {
            AgentShopScreen(navController, it.arguments!!.getString("host")!!, it.arguments!!.getInt("companyId"))
        }
        composable(
            "skill_shop/{host}/{companyId}",
            arguments = listOf(navArgument("companyId") { type = NavType.IntType }),
        ) {
            SkillShopScreen(navController, it.arguments!!.getString("host")!!, it.arguments!!.getInt("companyId"))
        }
        composable(
            "models/{host}/{companyId}",
            arguments = listOf(navArgument("companyId") { type = NavType.IntType }),
        ) {
            ModelsScreen(navController, it.arguments!!.getString("host")!!, it.arguments!!.getInt("companyId"))
        }
        composable("settings") { SettingsScreen(navController) }
    }
}
