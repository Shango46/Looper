package com.looper.remote.service

import android.app.Service
import android.content.Intent
import android.os.IBinder
import com.looper.remote.ui.Session
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.Job
import kotlinx.coroutines.SupervisorJob
import kotlinx.coroutines.cancel
import kotlinx.coroutines.delay
import kotlinx.coroutines.isActive
import kotlinx.coroutines.launch

private const val NOTIFICATION_ID = 1
private const val POLL_INTERVAL_MS = 20_000L

/**
 * Foreground service that polls every saved company's /approvals every ~20s and fires a local
 * notification for anything new. NOT Firebase push — accepted tradeoff (~20s latency).
 *
 * Disclosed limitation: Android 15 caps "dataSync" foreground services at 6 cumulative hours of
 * runtime per day; past that the system stops this service until the next day, so "notify me as
 * long as I'm logged in" is really "...for up to 6 hours of foreground app use per day."
 */
class ApprovalPollingService : Service() {
    private val scope = CoroutineScope(SupervisorJob() + Dispatchers.IO)
    private var pollJob: Job? = null

    override fun onCreate() {
        super.onCreate()
        ensureNotificationChannels(this)
    }

    override fun onStartCommand(intent: Intent?, flags: Int, startId: Int): Int {
        val companyCount = Session.store.load().size
        startForeground(NOTIFICATION_ID, buildServiceNotification(this, companyCount))

        if (pollJob == null || pollJob?.isActive != true) {
            pollJob = scope.launch { pollLoop() }
        }
        return START_STICKY
    }

    private suspend fun pollLoop() {
        while (scope.isActive) {
            val companies = Session.store.load()
            for (company in companies) {
                try {
                    val approvals = Session.clientFor(company).listApprovals()
                    val lastNotified = Session.store.getLastNotifiedApprovalId(company)
                    val newOnes = approvals.filter { it.id > lastNotified }
                    for (approval in newOnes) {
                        showApprovalNotification(this@ApprovalPollingService, company, approval)
                    }
                    val maxId = approvals.maxOfOrNull { it.id } ?: lastNotified
                    if (maxId > lastNotified) {
                        Session.store.setLastNotifiedApprovalId(company, maxId)
                    }
                } catch (e: Exception) {
                    // Skip this company this cycle (offline/unreachable/code rotated) — try again
                    // next poll rather than failing the whole service over one company.
                }
            }
            delay(POLL_INTERVAL_MS)
        }
    }

    override fun onDestroy() {
        pollJob?.cancel()
        scope.cancel()
        super.onDestroy()
    }

    override fun onBind(intent: Intent?): IBinder? = null
}
