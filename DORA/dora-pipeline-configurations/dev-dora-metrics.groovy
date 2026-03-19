jte {
    allow_scm_jenkinsfile = false
    pipeline_template = 'dora-metrics/dora-metrics-pipeline-template.groovy'
}

libraries {
    dora
    jenkins {
        agent_label = 'linux'
        clean_job_workspace = true
    }
}

dora {
    html_template_url = 'https://TU_HTML_TEMPLATE.html'
}

keywords {
    execution {
        time = 10
        units = 'MINUTES'
    }

    job_environments = ''

    log_rotator = '30'
}