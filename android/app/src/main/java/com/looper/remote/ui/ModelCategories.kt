package com.looper.remote.ui

import com.looper.remote.data.ModelItem

val MODEL_CATEGORIES = listOf(
    "all"    to "All",
    "text"   to "Text",
    "vision" to "Vision",
    "video"  to "Video",
    "image"  to "Image Gen",
    "audio"  to "Audio",
    "free"   to "Free",
)

fun modalityCategory(modality: String?): String {
    if (modality == null) return "text"
    val parts = modality.split("->")
    val inputs  = parts.getOrElse(0) { "" }
    val outputs = parts.getOrElse(1) { "" }
    return when {
        "image" in outputs || "video" in outputs           -> "image"
        "audio" in outputs && "text" !in outputs           -> "audio"
        "video" in inputs                                  -> "video"
        "image" in inputs                                  -> "vision"
        "audio" in inputs && "text" !in inputs             -> "audio"
        else                                               -> "text"
    }
}

fun ModelItem.isFree() =
    (pricingPrompt?.toDoubleOrNull() ?: 1.0) == 0.0 &&
    (pricingCompletion?.toDoubleOrNull() ?: 1.0) == 0.0

fun List<ModelItem>.filterByCategory(cat: String) = filter { m ->
    when (cat) {
        "all"  -> true
        "free" -> m.isFree()
        else   -> modalityCategory(m.modality) == cat
    }
}
