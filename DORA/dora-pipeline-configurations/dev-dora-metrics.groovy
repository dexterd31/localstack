jte {
    allow_scm_jenkinsfile = false
    pipeline_template = 'dora-metrics/dora-metrics-pipeline-template.groovy'
}

libraries {
    jenkins {
        agent_label = 'linux'
        clean_job_workspace = true
    }
}

dora {
    html_template_url = 'https://'
}

keywords {
    execution {
        time = 10
        units = 'MINUTES'
    }

    jenkins_api_url = 'https://'

    job_environments = [
        // Definir ambientes aquí si aplica
    ]

    // No necesitamos variables aquí; la credencial se pasa como parámetro.
    log_rotator = '30'
}