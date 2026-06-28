package com.looper.remote

import java.net.Inet4Address
import java.net.NetworkInterface

object TailscaleDetector {

    /** True when a Tailscale VPN interface is up (100.64.0.0/10 address present). */
    fun isActive(): Boolean = getIp() != null

    /** The device's own Tailscale IPv4 address, or null when not connected. */
    fun getIp(): String? = try {
        NetworkInterface.getNetworkInterfaces()
            ?.asSequence()
            ?.filter { it.isUp && !it.isLoopback }
            ?.flatMap { it.inetAddresses.asSequence() }
            ?.filterIsInstance<Inet4Address>()
            ?.map { it.hostAddress ?: "" }
            ?.firstOrNull { isTailscaleRange(it) }
    } catch (_: Exception) {
        null
    }

    private fun isTailscaleRange(ip: String): Boolean {
        val p = ip.split(".").mapNotNull { it.toIntOrNull() }
        // Tailscale uses 100.64.0.0/10: first byte 100, second byte 64–127
        return p.size == 4 && p[0] == 100 && p[1] in 64..127
    }
}
