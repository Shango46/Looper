package com.looper.remote.service

import android.app.NotificationChannel
import android.app.NotificationManager
import android.app.PendingIntent
import android.content.Context
import android.content.Intent
import androidx.core.app.NotificationCompat
import com.looper.remote.MainActivity

object NotificationHelper {
    const val CHANNEL_APPROVALS = "looper_approvals"
    const val CHANNEL_SERVICE = "looper_service"

    fun createChannels(context: Context) {
        val nm = context.getSystemService(Context.NOTIFICATION_SERVICE) as NotificationManager
        nm.createNotificationChannel(
            NotificationChannel(CHANNEL_APPROVALS, "Approval Requests", NotificationManager.IMPORTANCE_HIGH).apply {
                description = "Notifies when an agent requires approval to proceed."
            }
        )
        nm.createNotificationChannel(
            NotificationChannel(CHANNEL_SERVICE, "Background Service", NotificationManager.IMPORTANCE_MIN).apply {
                description = "Keeps the approval polling service running."
            }
        )
    }

    fun buildServiceNotification(context: Context) =
        NotificationCompat.Builder(context, CHANNEL_SERVICE)
            .setContentTitle("Looper Remote")
            .setContentText("Monitoring for approval requests…")
            .setSmallIcon(android.R.drawable.ic_menu_rotate)
            .setOngoing(true)
            .setSilent(true)
            .build()

    fun showApprovalNotification(context: Context, host: String, companyId: Int, count: Int) {
        val intent = Intent(context, MainActivity::class.java).apply {
            putExtra("deeplink_host", host)
            putExtra("deeplink_company_id", companyId)
            flags = Intent.FLAG_ACTIVITY_SINGLE_TOP or Intent.FLAG_ACTIVITY_CLEAR_TOP
        }
        val pi = PendingIntent.getActivity(context, companyId, intent, PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_IMMUTABLE)
        val notif = NotificationCompat.Builder(context, CHANNEL_APPROVALS)
            .setContentTitle("$count approval${if (count == 1) "" else "s"} waiting")
            .setContentText("Tap to review in Looper Remote.")
            .setSmallIcon(android.R.drawable.ic_dialog_alert)
            .setAutoCancel(true)
            .setContentIntent(pi)
            .build()
        val nm = context.getSystemService(Context.NOTIFICATION_SERVICE) as NotificationManager
        nm.notify(companyId, notif)
    }

    fun cancelApprovalNotification(context: Context, companyId: Int) {
        (context.getSystemService(Context.NOTIFICATION_SERVICE) as NotificationManager).cancel(companyId)
    }
}
