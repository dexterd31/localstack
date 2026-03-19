properties([
    buildDiscarder(logRotator(numToKeepStr: log_rotator)),
    disableConcurrentBuilds(),
    [
        $class: 'EnvInjectJobProperty',
        info: [
            loadFilesFromMaster: false,
            propertiesContent: job_environments,
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

// Timeout (valor provisto por el config)
timeout(time: execution.time, unit: execution.units) {

    def metrics = doraFetchLeadTime(
        params.JENKINS_API_URL,
        params.JENKINS_API_CREDS
    )

    def htmlContent = doraRenderHtml(
        dora.html_template_url,
        metrics
    )

    def fileName = "dora-metrics-${env.BUILD_NUMBER}.html"

    writeFile file: fileName, text: htmlContent

    archiveArtifacts artifacts: fileName, fingerprint: true

    echo "Métrica DORA (Lead Time) obtenida y guardada en ${fileName}"
}