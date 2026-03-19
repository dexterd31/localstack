def call() {

    stage('DORA - Fetch Lead Time') {

        // 1. Obtener commit time real
        def commitTime = sh(
            script: "git log -1 --format=%ct",
            returnStdout: true
        ).trim().toLong() * 1000

        // 2. Deploy time (ahora)
        def deployTime = System.currentTimeMillis()

        // 3. Calcular métrica
        def metrics = new org.jenkinsci.plugins.dora.DoraMetrics()
            .calculateLeadTime(commitTime, deployTime)

        // 4. Guardar en contexto global
        binding.setVariable("DORA_METRICS", metrics)

        echo "✅ Lead Time calculado: ${metrics.leadTimeHuman}"
    }
}