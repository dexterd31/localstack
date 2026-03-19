package jte.dora.constants

class DoraMetrics implements Serializable {

    Map calculateLeadTime(long commitTime, long deployTime) {
        long leadTimeMs = deployTime - commitTime

        return [
            leadTimeMs    : leadTimeMs,
            leadTimeHuman : formatDuration(leadTimeMs),
            commitTime    : commitTime,
            deployTime    : deployTime,
            generatedAtISO: java.time.Instant.now().toString()
        ]
    }

    private String formatDuration(long ms) {
        long seconds = ms / 1000
        long minutes = seconds / 60
        long hours = minutes / 60
        long days = hours / 24

        long remSec = seconds % 60
        long remMin = minutes % 60
        long remHr = hours % 24

        List parts = []

        if (days) parts << "${days}d"
        if (remHr) parts << "${remHr}h"
        if (remMin) parts << "${remMin}m"
        if (remSec) parts << "${remSec}s"

        return parts ? parts.join(" ") : "0s"
    }
}