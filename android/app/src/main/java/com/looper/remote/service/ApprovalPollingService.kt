package com.looper.remote.service

import android.app.Service
import android.content.Intent
import android.os.IBinder
import com.looper.remote.data.SavedCompaniesStore
import com.looper.remote.ui.Session
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.SupervisorJob
import kotlinx.coroutines.cancel
import kotlinx.coroutines.delay
import kotlinx.coroutines.currentCoroutineContext
import kotlinx.coroutines.isActive
import kotlinx.coroutines.launch

class ApprovalPollingService : Service() {
    private val scope = CoroutineScope(Dispatchers.IO + SupervisorJob())
    private val notified = mutableMapOf<String, Int>()  // key -> last notified count

    override fun onCreate() {
        super.onCreate()
        NotificationHelper.createChannels(this)
        startForeground(1, NotificationHelper.buildServiceNotification(this))
        scope.launch { pollLoop() }
    }

    override fun onStartCommand(intent: Intent?, flags: Int, startId: Int): Int = START_STICKY

    override fun onDestroy() {
        scope.cancel()
        super.onDestroy()
    }

    override fun onBind(intent: Intent?): IBinder? = null

    private suspend fun pollLoop() {
        while (currentCoroutineContext().isActive) {
            poll()
            delay(30_000L)
        }
    }

    private suspend fun poll() {
        val companies = Session.store.load()
        for (company in companies) {
            try {
                val count = Session.clientFor(company).pendingApprovalCount()
                val key = SavedCompaniesStore.keyFor(company)
                val prev = notified[key] ?: 0
                if (count > 0 && count != prev) {
                    NotificationHelper.showApprovalNotification(this, company.host, company.companyId, count)
                } else if (count == 0 && prev > 0) {
                    NotificationHelper.cancelApprovalNotification(this, company.companyId)
                }
                notified[key] = count
            } catch (_: Exception) {
                // Server unreachable or token expired — skip silently
            }
        }
    }
}
