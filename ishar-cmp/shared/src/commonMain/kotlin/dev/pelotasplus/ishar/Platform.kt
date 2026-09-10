package dev.pelotasplus.ishar

interface Platform {
    val name: String
}

expect fun getPlatform(): Platform