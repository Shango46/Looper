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
import com.looper.remote.ui.screens.ApprovalsScreen
import com.looper.remote.ui.screens.CompanyActivityScreen
import com.looper.remote.ui.screens.CompanyHomeScreen
import com.looper.remote.ui.screens.FileBrowserScreen
import com.looper.remote.ui.screens.McpServersScreen
import com.looper.remote.ui.screens.ReconnectScreen
import com.looper.remote.ui.screens.SkillsScreen
import com.looper.remote.ui.screens.SwitcherScreen

data class DeepLinkTarget(val host: String, val companyId: Int)

class MainActivity : ComponentActivity() {
    private val notificationPermissionLauncher =
        registerForActivityResult(ActivityResultContracts.RequestPermission()) {
            Session.syncPollingService(this)
        }

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        Session.init(this)
        requestNotificationPermissionThenSync()

        setContent {
            MaterialTheme {
                Surface(modifier = Modifier) {
                    LooperRemoteNavHost(deepLinkFromIntent(intent))
                }
            }
        }
    }

    override fun onResume() {
        super.onResume()
        // Re-arm the polling service on every foreground, so it recovers promptly after the
        // Android 15 dataSync 6-hour/day cap (or any other reason it stopped) rather than
        // staying down until the user happens to notice and remove/re-add a company.
        if (Build.VERSION.SDK_INT < Build.VERSION_CODES.TIRAMISU ||
            ContextCompat.checkSelfPermission(this, Manifest.permission.POST_NOTIFICATIONS) == PackageManager.PERMISSION_GRANTED
        ) {
            Session.syncPollingService(this)
        }
    }

    override fun onNewIntent(intent: Intent) {
        super.onNewIntent(intent)
        setIntent(intent)
        // Re-set content with the new deep link; simplest reliable way to react to a notification
        // tap while the Activity is already running, given the NavHost's graph is fixed at the
        // top of setContent.
        setContent {
            MaterialTheme {
                Surface(modifier = Modifier) {
                    LooperRemoteNavHost(deepLinkFromIntent(intent))
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
            val granted = ContextCompat.checkSelfPermission(this, Manifest.permission.POST_NOTIFICATIONS) ==
                PackageManager.PERMISSION_GRANTED
            if (granted) {
                Session.syncPollingService(this)
            } else {
                notificationPermissionLauncher.launch(Manifest.permission.POST_NOTIFICATIONS)
            }
        } else {
            Session.syncPollingService(this)
        }
    }
}

@Composable
fun LooperRemoteNavHost(deepLink: DeepLinkTarget? = null) {
    val navController: NavHostController = rememberNavController()
    var consumedDeepLink by remember { mutableStateOf(false) }

    LaunchedEffect(deepLink) {
        if (deepLink != null && !consumedDeepLink) {
            consumedDeepLink = true
            navController.navigate("approvals/${deepLink.host}/${deepLink.companyId}")
        }
    }

    NavHost(navController = navController, startDestination = "switcher") {
        composable("switcher") {
            SwitcherScreen(navController)
        }
        composable("add") {
            AddCompanyScreen(navController)
        }
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
            "agent/{host}/{companyId}/{agentId}",
            arguments = listOf(
                navArgument("companyId") { type = NavType.IntType },
                navArgument("agentId") { type = NavType.IntType },
            ),
        ) {
            AgentDetailScreen(
                navController,
                it.arguments!!.getString("host")!!,
                it.arguments!!.getInt("companyId"),
                it.arguments!!.getInt("agentId"),
            )
        }
        composable(
            "chat/{host}/{companyId}/{agentId}",
            arguments = listOf(
                navArgument("companyId") { type = NavType.IntType },
                navArgument("agentId") { type = NavType.IntType },
            ),
        ) {
            AgentChatScreen(
                navController,
                it.arguments!!.getString("host")!!,
                it.arguments!!.getInt("companyId"),
                it.arguments!!.getInt("agentId"),
            )
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
    }
}
