properties([
    buildDiscarder(logRotator(numToKeepStr: log_rotator)),
    disableConcurrentBuilds()
])

node {

    timeout(time: execution.time, unit: execution.units) {

        stage('DORA - Fetch Metrics') {
            def metrics = doraFetchLeadTime()

            env.DORA_METRICS_JSON = groovy.json.JsonOutput.toJson(metrics)
        }

        stage('DORA - Render HTML') {

            def metrics = new groovy.json.JsonSlurper()
                .parseText(env.DORA_METRICS_JSON)

            def htmlContent = doraRenderHtml(
                dora.html_template_url,
                metrics
            )

            def fileName = "dora-metrics-${env.BUILD_NUMBER}.html"

            writeFile file: fileName, text: htmlContent

            archiveArtifacts artifacts: fileName, fingerprint: true

            echo "📄 Métrica DORA (Lead Time) guardada en ${fileName}"
        }
    }
}