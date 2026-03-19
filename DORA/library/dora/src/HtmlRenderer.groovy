package jte.dora.constants

class HtmlRenderer {

    def renderHtml(String htmlTemplateUrl, Map metrics) {
        def rawHtml = new URL(htmlTemplateUrl).text

        return rawHtml
            .replaceAll('\\{\\{JOB_NAME\\}\\}', metrics.jobName ?: "N/A")
            .replaceAll('\\{\\{LEAD_TIME\\}\\}', metrics.leadTimeHuman ?: "0s")
            .replaceAll('\\{\\{COMMIT_TIME\\}\\}', new Date(metrics.commitTime).toString())
            .replaceAll('\\{\\{DEPLOY_TIME\\}\\}', new Date(metrics.deployTime).toString())
            .replaceAll('\\{\\{GENERATED_AT\\}\\}', metrics.generatedAtISO ?: "")
    }
}