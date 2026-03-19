def call(String apiUrl, String credentialsId) {

    def metrics = new org.jenkinsci.plugins.dora.DoraMetrics()
        .fetchLeadTime(apiUrl, credentialsId)

    // 🔥 Agregamos el nombre del job
    metrics.jobName = env.JOB_NAME

    return metrics
}