def call() {

    stage('DORA - Render HTML') {

        def metrics = binding.getVariable("DORA_METRICS")

        if (!metrics) {
            error "❌ No hay métricas DORA. Ejecuta doraFetchLeadTime primero."
        }

        def html = new org.jenkinsci.plugins.dora.HtmlRenderer()
            .renderHtml(dora.html_template_url, metrics)

        writeFile file: "dora-report.html", text: html

        echo "📄 Reporte generado: dora-report.html"
    }
}