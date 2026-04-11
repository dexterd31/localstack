application_environments {
  dev { ... }
  qa { ... }
  uat { ... }
}

jte {
  pipeline_template = 'mexico-microservice-pipeline-template.groovy'
}

keywords {
  component_name = params.PROYECT
  component_type = 'backend' // o 'frontend', 'library'
  // Para frontends
  frontend_build = true
  npm_source_path = 'frontend/src/main/claims/'
  // Para librerías
  library_subpath = 'APPCTRL/' // si aplica
}

// Esto reemplazaría la lógica del switch
deployment_routing {
  // Mapeo de (proyecto, ambiente) → (dominio, dominio2, serverGroup)
  rules = [
    [proyecto: 'Bancoppel', pattern: 'mx-pri-bancoppel-config-server', dominio_tipo: 'configvault', serverGroup: 'ServerGroup_Config_Server'],
    [proyecto: 'collections', pattern: 'mx-pri-configuration-service|mx-pri-documents-service|...', dominio_tipo: 'internalservices'],
    // etc.
  ]
}

libraries {
  maven { settings_config = 'MX_MAVEN_SETTINGS' }
  sonar { 
    server = 'SonarLAM'
    coverage_threshold = 95  // ¡Importante!
  }
  nodejs { version = '18' }
  // ...
}