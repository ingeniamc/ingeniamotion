@Library('cicd-lib@0.12') _

def SW_NODE = "windows-slave"
def ECAT_NODE = "ecat-test"
def ECAT_NODE_LOCK = "test_execution_lock_ecat"
def CAN_NODE = "canopen-test"
def CAN_NODE_LOCK = "test_execution_lock_can"

def LIN_DOCKER_IMAGE = "ingeniacontainers.azurecr.io/docker-python:1.5"
def WIN_DOCKER_IMAGE = "ingeniacontainers.azurecr.io/win-python-builder:1.6"

DEFAULT_PYTHON_VERSION = "3.9"

ALL_PYTHON_VERSIONS = "py39,py310,py311,py312"
RUN_PYTHON_VERSIONS = ""
PYTHON_VERSION_MIN = "py39"
def PYTHON_VERSION_MAX = "py312"

def BRANCH_NAME_MASTER = "master"
def DISTEXT_PROJECT_DIR = "doc/ingeniamotion"

WIRESHARK_DIR = "wireshark"
USE_WIRESHARK_LOGGING = ""
START_WIRESHARK_TIMEOUT_S = 10.0

FSOE_INSTALL_VERSION = ".[FSoE]"

coverage_stashes = []


def clearWiresharkLogs() {
    bat(script: 'del /f "%WIRESHARK_DIR%\\*.pcap"', returnStatus: true)
}

def archiveWiresharkLogs() {
    archiveArtifacts artifacts: "${WIRESHARK_DIR}\\*.pcap", allowEmptyArchive: true
}

def runTestHW(run_identifier, markers, setup_name, install_fsoe = false, extra_args = "") {
    try {
        timeout(time: 1, unit: 'HOURS') {
            def fsoe_package = null
            if (install_fsoe) {
                fsoe_package = FSOE_INSTALL_VERSION
            }

            def pythonVersions = RUN_PYTHON_VERSIONS.split(',')

            pythonVersions.each { version ->
                withEnv(["FSOE_PACKAGE=${fsoe_package}", "WIRESHARK_SCOPE=${params.WIRESHARK_LOGGING_SCOPE}", "CLEAR_WIRESHARK_LOG_IF_SUCCESSFUL=${params.CLEAR_SUCCESSFUL_WIRESHARK_LOGS}", "START_WIRESHARK_TIMEOUT_S=${START_WIRESHARK_TIMEOUT_S}"]) {
                    try {
                        bat "py -${DEFAULT_PYTHON_VERSION} -m tox -e ${version} -- " +
                                "-m \"${markers}\" " +
                                "--setup tests.setups.rack_specifiers.${setup_name} " +
                                "--job_name=\"${env.JOB_NAME}-#${env.BUILD_NUMBER}-${run_identifier}\" " +
                                "${extra_args}"
                    } catch (err) {
                        unstable(message: "Tests failed")
                    } finally {
                        junit "pytest_reports\\*.xml"
                        // Delete the junit after publishing it so it not re-published on the next stage
                        bat "del /S /Q pytest_reports\\*.xml"
                        // Save the coverage so it can be unified and published later
                        def coverage_stash = ".coverage_${run_identifier}_${version}"
                        bat "move .coverage ${coverage_stash}"
                        stash includes: coverage_stash, name: coverage_stash
                        coverage_stashes.add(coverage_stash)
                    }
                }
            }
        }
    } finally {
        archiveWiresharkLogs()
        clearWiresharkLogs()
    }
}

/* Build develop everyday 3 times starting at 19:00 UTC (21:00 Barcelona Time), running all python versions */
CRON_SETTINGS = BRANCH_NAME == "develop" ? '''0 19,21,23 * * * % PYTHON_VERSIONS=All''' : ""

pipeline {
    agent none
    options {
        timestamps()
    }
    triggers {
        parameterizedCron(CRON_SETTINGS)
    }
    parameters {
        choice(
                choices: ['MIN', 'MAX', 'MIN_MAX', 'All'],
                name: 'PYTHON_VERSIONS'
        )
        booleanParam(name: 'WIRESHARK_LOGGING', defaultValue: true, description: 'Enable Wireshark logging')
        choice(
                choices: ['function', 'module', 'session'],
                name: 'WIRESHARK_LOGGING_SCOPE'
        )
        booleanParam(name: 'CLEAR_SUCCESSFUL_WIRESHARK_LOGS', defaultValue: true, description: 'Clears Wireshark logs if the test passed')
    }
    stages {
        stage("Set env") {
            steps {
                script {
                    if (env.BRANCH_NAME == 'master') {
                        RUN_PYTHON_VERSIONS = ALL_PYTHON_VERSIONS
                    } else if (env.BRANCH_NAME.startsWith('release/')) {
                        RUN_PYTHON_VERSIONS = ALL_PYTHON_VERSIONS
                    } else {
                        if (env.PYTHON_VERSIONS == "MIN_MAX") {
                          RUN_PYTHON_VERSIONS = "${PYTHON_VERSION_MIN},${PYTHON_VERSION_MAX}"
                        } else if (env.PYTHON_VERSIONS == "MIN") {
                          RUN_PYTHON_VERSIONS = PYTHON_VERSION_MIN
                        } else if (env.PYTHON_VERSIONS == "MAX") {
                          RUN_PYTHON_VERSIONS = PYTHON_VERSION_MAX
                        } else if (env.PYTHON_VERSIONS == "All") {
                          RUN_PYTHON_VERSIONS = ALL_PYTHON_VERSIONS
                        } else { // Branch-indexing
                          RUN_PYTHON_VERSIONS = PYTHON_VERSION_MIN
                        }
                    }

                    if (params.WIRESHARK_LOGGING) {
                        USE_WIRESHARK_LOGGING = "--run_wireshark"
                    } else {
                        USE_WIRESHARK_LOGGING = ""
                    }
                }
            }
        }

        stage('Build and Tests') {
            parallel {
                stage('Virtual drive tests on Linux') {
                    agent {
                        docker {
                            label "worker"
                            image LIN_DOCKER_IMAGE
                        }
                    }
                    stages {
                        stage('Run no-connection tests') {
                            steps {
                                sh "python${DEFAULT_PYTHON_VERSION} -m tox -e ${RUN_PYTHON_VERSIONS} -- " +
                                    "-m virtual " +
                                    "--setup summit_testing_framework.setups.virtual_drive.TESTS_SETUP"
                            }
                            post {
                                always {
                                    junit "pytest_reports/*.xml"
                                }
                            }
                        }
                    }
                }

                stage('Build and publish') {
                    stages {
                        stage('Build') {
                            agent {
                                docker {
                                    label SW_NODE
                                    image WIN_DOCKER_IMAGE
                                }
                            }
                            stages {
                                stage('Build wheels') {
                                    steps {
                                        bat "py -${DEFAULT_PYTHON_VERSION} -m tox -e build"
                                        stash includes: 'dist\\*', name: 'build'
                                        archiveArtifacts artifacts: "dist\\*"
                                    }
                                }
                                stage('Make a static type analysis') {
                                    steps {
                                        bat "py -${DEFAULT_PYTHON_VERSION} -m tox -e type"
                                    }
                                }
                                stage('Check formatting') {
                                    steps {
                                        bat "py -${DEFAULT_PYTHON_VERSION} -m tox -e format"
                                    }
                                }
                                stage('Generate documentation') {
                                    steps {
                                        bat "py -${DEFAULT_PYTHON_VERSION} -m tox -e docs"
                                        bat """
                                            "C:\\Program Files\\7-Zip\\7z.exe" a -r docs.zip -w _docs -mem=AES256
                                        """
                                        stash includes: 'docs.zip', name: 'docs'
                                    }
                                }
                                stage("Run unit tests") {
                                    steps {
                                        bat """
                                            py -${DEFAULT_PYTHON_VERSION} -m tox -e ${RUN_PYTHON_VERSIONS} -- ^
                                            -m "not ethernet and not soem and not fsoe and not canopen and not virtual and not soem_multislave and not skip_testing_framework"
                                        """
                                    }
                                    post {
                                        always {
                                            bat "move .coverage .coverage_unit_tests"
                                            junit "pytest_reports\\*.xml"
                                            // Delete the junit after publishing it so it not re-published on the next stage
                                            bat "del /S /Q pytest_reports\\*.xml"
                                            stash includes: '.coverage_unit_tests', name: '.coverage_unit_tests'
                                            script {
                                                coverage_stashes.add(".coverage_unit_tests")
                                            }
                                        }
                                    }
                                }
                                stage("Run virtual drive tests") {
                                    steps {
                                        bat "py -${DEFAULT_PYTHON_VERSION} -m tox -e ${RUN_PYTHON_VERSIONS} -- " +
                                                "-m virtual " +
                                                "--setup summit_testing_framework.setups.virtual_drive.TESTS_SETUP "
                                    }
                                    post {
                                        always {
                                            bat "move .coverage .coverage_virtual"
                                            junit "pytest_reports\\*.xml"
                                            // Delete the junit after publishing it so it not re-published on the next stage
                                            bat "del /S /Q pytest_reports\\*.xml"
                                            stash includes: '.coverage_virtual', name: '.coverage_virtual'
                                            script {
                                                coverage_stashes.add(".coverage_virtual")
                                            }
                                        }
                                    }
                                }
                            }
                        }
                        stage('Publish documentation') {
                            when {
                                beforeAgent true
                                branch BRANCH_NAME_MASTER
                            }
                            agent {
                                label "worker"
                            }
                            steps {
                                unstash 'docs'
                                unzip zipFile: 'docs.zip', dir: '.'
                                publishDistExt("_docs", DISTEXT_PROJECT_DIR, false)
                            }
                        }
                        stage('Publish to pypi') {
                            when {
                                beforeAgent true
                                branch BRANCH_NAME_MASTER
                            }
                            agent {
                                docker {
                                    label 'worker'
                                    image "ingeniacontainers.azurecr.io/publisher:1.8"
                                }
                            }
                            steps {
                                unstash 'build'
                                publishPyPi("dist/*")
                            }
                        }
                    }
                }

                stage('HW Tests CanOpen and Ethernet') {
                    options {
                        lock(CAN_NODE_LOCK)
                    }
                    agent {
                        label CAN_NODE
                    }
                    stages {
                        stage ("Clear Wireshark logs") {
                            steps {
                                clearWiresharkLogs()
                            }
                        }
                        stage("CanOpen Everest") {
                            steps {
                                runTestHW("canopen_everest", "canopen and not skip_testing_framework", "CAN_EVE_SETUP")
                                runTestHW("canopen_everest_no_framework", "canopen and skip_testing_framework", "CAN_EVE_SETUP")
                            }
                        }
                        stage("Ethernet Everest") {
                            steps {
                                runTestHW("ethernet_everest", "ethernet", "ETH_EVE_SETUP", false, USE_WIRESHARK_LOGGING)
                            }
                        }
                        stage("CanOpen Capitan") {
                            steps {
                                runTestHW("canopen_capitan", "canopen and not skip_testing_framework", "CAN_CAP_SETUP")
                                runTestHW("canopen_capitan_no_framework", "canopen and skip_testing_framework", "CAN_EVE_SETUP")
                            }
                        }
                        stage("Ethernet Capitan") {
                            when {
                                // Remove this after fixing INGK-982
                                expression { false }
                            }
                            steps {
                                runTestHW("ethernet capitan", "ethernet", "ETH_CAP_SETUP", false, USE_WIRESHARK_LOGGING)
                            }
                        }
                    }
                }
                stage('Hw Tests Ethercat') {
                    options {
                        lock(ECAT_NODE_LOCK)
                    }
                    agent {
                        label ECAT_NODE
                    }
                    stages {
                        stage ("Clear Wireshark logs") {
                            steps {
                                clearWiresharkLogs()
                            }
                        }
                        stage("Ethercat Everest") {
                            when {
                                // Remove this after fixing INGK-983
                                expression { false }
                            }
                            steps {
                                runTestHW("ethercat_everest", "soem", "ECAT_EVE_SETUP", false, USE_WIRESHARK_LOGGING)
                            }
                        }
                        stage("Ethercat Capitan") {
                            steps {
                                runTestHW("ethercat_capitan", "soem", "ECAT_CAP_SETUP", false, USE_WIRESHARK_LOGGING)
                            }
                        }
                        stage("Safety Denali") {
                            steps {
                                runTestHW("fsoe_phase1", "fsoe", "ECAT_DEN_S_PHASE1_SETUP", true, USE_WIRESHARK_LOGGING)
                            }
                        }
                        stage("Ethercat Multislave") {
                            steps {
                                runTestHW("ethercat_multislave", "soem_multislave", "ECAT_MULTISLAVE_SETUP", false, USE_WIRESHARK_LOGGING)
                            }
                        }
                    }
                }
            }
        }

        stage('Publish coverage') {
            agent {
                docker {
                    label SW_NODE
                    image WIN_DOCKER_IMAGE
                }
            }
            steps {
                script {
                    def coverage_files = ""

                    for (coverage_stash in coverage_stashes) {
                        unstash coverage_stash
                        coverage_files += " " + coverage_stash
                    }
                    bat "py -${DEFAULT_PYTHON_VERSION} -m tox -e coverage -- ${coverage_files}"
                }
                recordCoverage(tools: [[parser: 'COBERTURA', pattern: 'coverage.xml']])
                archiveArtifacts artifacts: '*.xml'
            }
        }
    }
}
