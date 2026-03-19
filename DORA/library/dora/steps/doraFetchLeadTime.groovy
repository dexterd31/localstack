def call() {

    def commitTime = sh(
        script: "git log -1 --format=%ct",
        returnStdout: true
    ).trim().toLong() * 1000

    def deployTime = System.currentTimeMillis()

    def metrics = new jte.dora.constants.DoraMetrics()
        .calculateLeadTime(commitTime, deployTime)

    metrics.jobName = env.JOB_NAME

    return metrics
}