properties([
    buildDiscarder(logRotator(numToKeepStr: log_rotator)),
    disableConcurrentBuilds(),
    [
        $class: 'EnvInjectJobProperty',
        info: [
            loadFilesFromMaster: false,
            propertiesContent: job_environments ?: '',
            keepBuildVariables: true,
            keepJenkinsSystemVariables: true
        ],
        on: true
    ],
    parameters([
        string(
            name: 'JENKINS_API_URL',
            description: 'URL completa de la API de Jenkins que devuelve los builds',
            defaultValue: dora.jenkins_api_url,
            trim: true
        ),
        credentials(
            name: 'JENKINS_API_CREDS',
            description: 'Credenciales (username + token) para acceder a la API de Jenkins',
            defaultValue: '',
            required: true
        )
    ])
])

timeout(time: execution.time, unit: execution.units) {

    stage('DORA - Fetch Metrics') {
        def metrics = doraFetchLeadTime(
            params.JENKINS_API_URL,
            params.JENKINS_API_CREDS
        )

        // Guardamos para siguiente stage
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