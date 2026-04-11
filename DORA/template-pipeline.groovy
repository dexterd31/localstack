properties([
    buildDiscarder(logRotator(numToKeepStr: log_rotator)),
    disableConcurrentBuilds()
])



timeout(time: execution.time, unit: execution.units) {
    // Checkout
    bitbucket_server_checkout(params.BRANCH)

    // Build con lógica condicional según component_type
    build_component_mexico()  // step personalizado

    // Tests
    run_tests()

    // SonarQube con quality gate y coverage check
    run_sonar_analysis()
    check_quality_gate_with_coverage(95)

    // Deploy (usando la lógica de routing)
    def route = get_deployment_route(params.PROYECT, ambiente)
    deploy_to_websphere_or_jboss(route)
}
