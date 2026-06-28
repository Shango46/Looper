package com.looper.remote

import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.activity.enableEdgeToEdge
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Surface
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import com.looper.remote.ui.screens.NoTailscaleScreen
import com.looper.remote.ui.screens.ServerSetupScreen
import com.looper.remote.ui.screens.WebViewScreen

class MainActivity : ComponentActivity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        enableEdgeToEdge()
        setContent {
            MaterialTheme {
                Surface(modifier = Modifier) {
                    LooperRemoteApp()
                }
            }
        }
    }
}

private sealed class Screen {
    data object CheckingTailscale : Screen()
    data object NoTailscale : Screen()
    data object ServerSetup : Screen()
    data class WebView(val url: String) : Screen()
}

@Composable
private fun LooperRemoteApp() {
    val context = LocalContext.current
    val prefs = remember { ServerPrefs(context) }
    var screen by remember { mutableStateOf<Screen>(Screen.CheckingTailscale) }

    // Initial routing: check Tailscale, then decide where to send the user.
    LaunchedEffect(Unit) {
        screen = resolveScreen(prefs)
    }

    when (val s = screen) {
        Screen.CheckingTailscale -> {
            // Blank surface while we check — typically sub-millisecond on device.
        }

        Screen.NoTailscale -> NoTailscaleScreen(
            onRefresh = { screen = resolveScreen(prefs) },
        )

        Screen.ServerSetup -> ServerSetupScreen(
            existingUrl = prefs.serverUrl,
            onConnect = { url ->
                prefs.serverUrl = url
                screen = Screen.WebView(url)
            },
        )

        is Screen.WebView -> WebViewScreen(
            serverUrl = s.url,
            onChangeServer = { screen = Screen.ServerSetup },
        )
    }
}

private fun resolveScreen(prefs: ServerPrefs): Screen {
    if (!TailscaleDetector.isActive()) return Screen.NoTailscale
    val url = prefs.serverUrl ?: return Screen.ServerSetup
    return Screen.WebView(url)
}
