package com.looper.remote.ui

import android.content.Context
import android.content.Intent
import androidx.core.content.ContextCompat
import com.looper.remote.data.ApiException
import com.looper.remote.data.LooperApiClient
import com.looper.remote.data.SavedCompaniesStore
import com.looper.remote.data.SavedCompany
import com.looper.remote.service.ApprovalPollingService

/** App-wide singleton holding the saved-company store and one reusable API client per
 * connected company (keyed by "host::companyId"). Kept deliberately simple (no DI framework)
 * given the small scope of this app. */
object Session {
    lateinit var store: SavedCompaniesStore
        private set

    private val clients = mutableMapOf<String, LooperApiClient>()

    fun init(context: Context) {
        if (!::store.isInitialized) {
            store = SavedCompaniesStore(context.applicationContext)
        }
    }

    fun clientFor(company: SavedCompany): LooperApiClient {
        val key = SavedCompaniesStore.keyFor(company)
        return clients.getOrPut(key) { LooperApiClient(company.host, company.token) }
    }

    fun updateToken(company: SavedCompany, newToken: String) {
        val key = SavedCompaniesStore.keyFor(company)
        clients[key]?.token = newToken
        store.upsert(company.copy(token = newToken))
    }

    fun forget(company: SavedCompany) {
        val key = SavedCompaniesStore.keyFor(company)
        clients.remove(key)
        store.remove(company.host, company.companyId)
    }

    /** Starts (or stops, if no companies remain) the approval-polling foreground service.
     * Call after any change to the saved-company list — add, reconnect, or remove. */
    fun syncPollingService(context: Context) {
        val intent = Intent(context, ApprovalPollingService::class.java)
        if (store.load().isNotEmpty()) {
            ContextCompat.startForegroundService(context, intent)
        } else {
            context.stopService(intent)
        }
    }

    /** True if this exception means the saved code is no longer valid and the user must
     * re-enter a new one (vs. a generic/transient failure). */
    fun needsReconnect(e: Throwable): Boolean =
        e is ApiException && (e.errorCode == "code_changed" || e.errorCode == "access_disabled" || e.errorCode == "invalid_token")
}
