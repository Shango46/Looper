package com.looper.remote.ui

import android.content.Context
import android.content.Intent
import com.looper.remote.data.ApiClient
import com.looper.remote.data.SavedCompany
import com.looper.remote.data.SavedCompaniesStore
import com.looper.remote.service.ApprovalPollingService

object Session {
    lateinit var store: SavedCompaniesStore
    private val clients = mutableMapOf<String, ApiClient>()

    fun init(context: Context) {
        store = SavedCompaniesStore(context)
    }

    fun clientFor(company: SavedCompany): ApiClient =
        clients.getOrPut(SavedCompaniesStore.keyFor(company)) {
            ApiClient(company.host, company.token)
        }

    fun forget(company: SavedCompany) {
        store.remove(company)
        clients.remove(SavedCompaniesStore.keyFor(company))
    }

    fun syncPollingService(context: Context) {
        val companies = store.load()
        val intent = Intent(context, ApprovalPollingService::class.java)
        if (companies.isEmpty()) {
            context.stopService(intent)
        } else {
            context.startForegroundService(intent)
        }
    }
}
