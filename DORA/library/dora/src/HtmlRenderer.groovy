package org.jenkinsci.plugins.dora

class HtmlRenderer {

    def renderHtml(String htmlTemplateUrl, Map metrics) {
        def rawHtml = new URL(htmlTemplateUrl).text

        return rawHtml
            .replaceAll('\\{\\{LEAD_TIME\\}\\}', metrics.leadTimeHuman ?: "0s")
            .replaceAll('\\{\\{COMMIT_TIME\\}\\}', new Date(metrics.commitTime).toString())
            .replaceAll('\\{\\{DEPLOY_TIME\\}\\}', new Date(metrics.deployTime).toString())
            .replaceAll('\\{\\{GENERATED_AT\\}\\}', formatTimestamp(metrics.generatedAtISO))
    }

    private String formatTimestamp(String iso) {
        def instant = java.time.Instant.parse(iso)

        def fmt = java.time.format.DateTimeFormatter
            .ofPattern('yyyy-MM-dd HH:mm:ss')
            .withZone(java.time.ZoneId.of("UTC"))

        return fmt.format(instant) + " UTC"
    }
}