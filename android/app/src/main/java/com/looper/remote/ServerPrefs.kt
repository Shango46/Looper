package com.looper.remote

import android.content.Context

class ServerPrefs(context: Context) {
    private val p = context.getSharedPreferences("looper_remote", Context.MODE_PRIVATE)

    /** Full URL of the Looper server, e.g. "http://100.x.x.x:8731" */
    var serverUrl: String?
        get() = p.getString("server_url", null)
        set(v) = p.edit().putString("server_url", v).apply()

    /** Version tag to skip when prompting for updates (user chose "Later" before). */
    var skippedVersion: String?
        get() = p.getString("skip_version", null)
        set(v) = p.edit().putString("skip_version", v).apply()
}
