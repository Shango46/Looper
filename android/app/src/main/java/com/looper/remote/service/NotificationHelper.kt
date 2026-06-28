package com.looper.remote.service

import android.app.NotificationChannel
import android.app.NotificationManager
import android.app.PendingIntent
import android.content.Context
import android.content.Intent
import android.os.Build
import androidx.core.app.NotificationCompat
import com.looper.remote.MainActivity
import com.looper.remote.data.ApprovalItem
import com.looper.remote.data.SavedCompany

const val APPROVALS_CHANNEL_ID = "looper_approvals"
const val SERVICE_CHANNEL_ID = "looper_service"

fun ensureNotificationChannels(context: Context) {
    val manager = context.getSystemService(NotificationManager::class.java)
    manager.createNotificationChannel(
        NotificationChannel(APPROVALS_CHANNEL_ID, "Approval requests", NotificationManager.IMPORTANCE_HIGH).apply {
            description = "Notifies you when an agent needs approval for a risky action or skill grant."
        },
    )
    manager.createNotificationChannel(
        NotificationChannel(SERVICE_CHANNEL_ID, "Background watcher", NotificationManager.IMPORTANCE_MIN).apply {
            description = "Persistent notification while Looper Remote watches for approvals."
        },
    )
}

fun buildServiceNotification(context: Context, companyCount: Int): android.app.Notification {
    return NotificationCompat.Builder(context, SERVICE_CHANNEL_ID)
        .setContentTitle("Looper Remote")
        .setContentText("Watching $companyCount compan${if (companyCount == 1) "y" else "ies"} for approvals")
        .setSmallIcon(android.R.drawable.ic_popup_sync)
        .setOngoing(true)
        .setPriority(NotificationCompat.PRIORITY_MIN)
        .build()
}

fun showApprovalNotification(context: Context, company: SavedCompany, approval: ApprovalItem) {
    val deepLinkIntent = Intent(context, MainActivity::class.java).apply {
        flags = Intent.FLAG_ACTIVITY_NEW_TASK or Intent.FLAG_ACTIVITY_CLEAR_TOP
        putExtra("deeplink_host", company.host)
        putExtra("deeplink_company_id", company.companyId)
        putExtra("deeplink_route", "approvals")
    }
    val pendingIntent = PendingIntent.getActivity(
        context,
        approval.id,
        deepLinkIntent,
        PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_IMMUTABLE,
    )

    val what = if (approval.kind == "skill_grant") "wants to use a new skill" else "needs approval for a risky action"
    val notification = NotificationCompat.Builder(context, APPROVALS_CHANNEL_ID)
        .setContentTitle(company.companyName)
        .setContentText("An agent $what")
        .setSmallIcon(android.R.drawable.ic_dialog_alert)
        .setPriority(NotificationCompat.PRIORITY_HIGH)
        .setAutoCancel(true)
        .setContentIntent(pendingIntent)
        .build()

    val manager = context.getSystemService(NotificationManager::class.java)
    manager.notify(approval.id, notification)
}
