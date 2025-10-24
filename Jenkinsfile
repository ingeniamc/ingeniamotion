@Library('cicd-lib@0.16') _

def SW_NODE = "windows-slave"
def ECAT_NODE = "ecat-test"
def ECAT_NODE_LOCK = "test_execution_lock_ecat"
def CAN_NODE = "canopen-test"
def CAN_NODE_LOCK = "test_execution_lock_can"

def LIN_DOCKER_IMAGE = "ingeniacontainers.azurecr.io/docker-python:1.6"
def WIN_DOCKER_IMAGE = "ingeniacontainers.azurecr.io/win-python-builder:1.7"

WIN_DOCKER_TMP_PATH = "C:\\Users\\ContainerAdministrator\\ingeniamotion"
LIN_DOCKER_TMP_PATH = "/tmp/ingeniamotion"

DEFAULT_PYTHON_VERSION = "3.9"

ALL_PYTHON_VERSIONS = "3.9,3.10,3.11,3.12"
RUN_PYTHON_VERSIONS = ""
PYTHON_VERSION_MIN = "3.9"
def PYTHON_VERSION_MAX = "3.12"

def BRANCH_NAME_MASTER = "master"
def DISTEXT_PROJECT_DIR = "doc/ingeniamotion"

WIRESHARK_DIR = "wireshark"
USE_WIRESHARK_LOGGING = ""
START_WIRESHARK_TIMEOUT_S = 10.0
FSOE_MAPS_DIR = "fsoe_maps"

coverage_stashes = []

def reassignFilePermissions() {
    if (isUnix()) {
        sh 'chmod -R 777 .'
    }
}

def clearWiresharkLogs() {
    bat(script: 'del /f "%WIRESHARK_DIR%\\*.pcap"', returnStatus: true)
}

def archiveWiresharkLogs() {
    archiveArtifacts artifacts: "${WIRESHARK_DIR}\\*.pcap", allowEmptyArchive: true
}

def runTestHW(run_identifier, markers, setup_name, extra_args = "") {
    try {
        timeout(time: 1, unit: 'HOURS') {
            def pythonVersions = RUN_PYTHON_VERSIONS.split(',')
            pythonVersions.each { version ->
                withEnv(["WIRESHARK_SCOPE=${params.WIRESHARK_LOGGING_SCOPE}", "CLEAR_WIRESHARK_LOG_IF_SUCCESSFUL=${params.CLEAR_SUCCESSFUL_WIRESHARK_LOGS}", "START_WIRESHARK_TIMEOUT_S=${START_WIRESHARK_TIMEOUT_S}"]) {
                    try {
                        bat """
                            call .venv${version}/Scripts/activate
                            poetry run poe tests ^
                                --import-mode=importlib ^
                                --cov=ingeniamotion ^
                                --junitxml=pytest_reports/junit-tests-${version}.xml ^
                                --junit-prefix=${version} ^
                                -m \"${markers}\" ^
                                --setup tests.setups.rack_specifiers.${setup_name} ^
                                --job_name=\"${env.JOB_NAME}-#${env.BUILD_NUMBER}-${run_identifier}\" ^
                                ${extra_args}
                        """
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

def runPython(command, py_version = DEFAULT_PYTHON_VERSION) {
    if (isUnix()) {
        sh "python${py_version} -I -m ${command}"
    } else {
        bat "py -${py_version} -I -m ${command}"
    }
}

def createVirtualEnvironments(String workingDir = null, String pythonVersionList = "") {
    def versions = pythonVersionList?.trim() ? pythonVersionList : RUN_PYTHON_VERSIONS
    def pythonVersions = versions.split(',')
    // Ensure DEFAULT_PYTHON_VERSION is included if not already present
    if (!pythonVersions.contains(DEFAULT_PYTHON_VERSION)) {
        pythonVersions = pythonVersions + [DEFAULT_PYTHON_VERSION]
    }
    pythonVersions.each { version ->
        def venvName = ".venv${version}"
        def cdCmd = workingDir ? "cd ${workingDir}" : ""
        if (isUnix()) {
            sh """
                ${cdCmd}
                python${version} -m venv --without-pip ${venvName}
                . ${venvName}/bin/activate
                poetry sync --all-groups
                deactivate
            """
        } else {
            bat """
                ${cdCmd}
                py -${version} -m venv ${venvName}
                call ${venvName}/Scripts/activate
                poetry sync --all-groups --extras fsoe
                deactivate
            """
        }
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
        choice(
            choices: [
                '.*',
                'virtual_drive_tests',
                'canopen.*',
                'ethernet.*',
                'canopen_everest.*',
                'canopen_capitan.*',
                'ethernet_everest.*',
                'ethernet_capitan.*',
                'ethercat.*',
                'ethercat_everest.*',
                'ethercat_capitan.*',
                'ethercat_multislave.*',
                'fsoe.*',
                'fsoe_phase1.*',
                'fsoe_phase2.*'
            ],
            name: 'run_test_stages',
            description: 'Regex pattern for which testing stage or substage to run (e.g. "fsoe_.*", "ethercat_everest", ".*" for all)'
        )
        booleanParam(name: 'WIRESHARK_LOGGING', defaultValue: false, description: 'Enable Wireshark logging')
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
                    when {
                        expression { "virtual_drive_tests" ==~ params.run_test_stages }
                    }
                    agent {
                        docker {
                            label "worker"
                            image LIN_DOCKER_IMAGE
                            args '-u root:root'
                        }
                    }
                    stages {
                        stage('Move workspace') {
                            steps {
                                script {
                                    sh """
                                        mkdir -p ${LIN_DOCKER_TMP_PATH}
                                        cp -r ${env.WORKSPACE}/. ${LIN_DOCKER_TMP_PATH}
                                    """
                                }
                            }
                        }
                        stage('Create virtual environments') {
                            steps {
                                script {
                                    createVirtualEnvironments(LIN_DOCKER_TMP_PATH)
                                }
                            }
                        }
                        stage('Run no-connection tests') {
                            steps {
                                script {
                                    def pythonVersions = RUN_PYTHON_VERSIONS.split(',')
                                    pythonVersions.each { version ->
                                        sh """
                                            cd ${LIN_DOCKER_TMP_PATH}
                                            . .venv${version}/bin/activate
                                            poetry run poe tests --junitxml=pytest_reports/junit-tests-${version}.xml --junit-prefix=${version} -m virtual --setup summit_testing_framework.setups.virtual_drive.TESTS_SETUP
                                            deactivate
                                        """
                                    }
                                }
                            }
                            post {
                                always {
                                    sh """
                                        mkdir -p pytest_reports
                                        cp ${LIN_DOCKER_TMP_PATH}/pytest_reports/* pytest_reports/
                                    """
                                    junit 'pytest_reports/*.xml'
                                }
                            }
                        }
                    }
                    post {
                        always {
                            reassignFilePermissions()
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
                                stage('Move workspace') {
                                    steps {
                                        bat "XCOPY ${env.WORKSPACE} ${WIN_DOCKER_TMP_PATH} /s /i /y /e /h"
                                    }
                                }
                                stage('Create virtual environments') {
                                    steps {
                                        script {
                                            createVirtualEnvironments(WIN_DOCKER_TMP_PATH)
                                        }
                                    }
                                }
                                stage('Build wheels') {
                                    environment {
                                        POETRY_DYNAMIC_VERSIONING_BYPASS = getPythonVersionForPr()
                                    }
                                    steps {
                                        bat """
                                            cd ${WIN_DOCKER_TMP_PATH}
                                            call .venv${DEFAULT_PYTHON_VERSION}/Scripts/activate
                                            poetry run poe build
                                            XCOPY dist ${env.WORKSPACE}\\dist /s /i
                                        """
                                        stash includes: 'dist\\*', name: 'build'
                                        archiveArtifacts artifacts: "dist\\*"
                                    }
                                }
                                stage('Make a static type analysis') {
                                    steps {
                                        bat """
                                            cd ${WIN_DOCKER_TMP_PATH}
                                            call .venv${DEFAULT_PYTHON_VERSION}/Scripts/activate
                                            poetry run poe type
                                        """
                                    }
                                }
                                stage('Check formatting') {
                                    steps {
                                        bat """
                                            cd ${WIN_DOCKER_TMP_PATH}
                                            call .venv${DEFAULT_PYTHON_VERSION}/Scripts/activate
                                            poetry run poe format
                                        """
                                    }
                                }
                                stage('Generate documentation') {
                                    steps {
                                        bat """
                                            cd ${WIN_DOCKER_TMP_PATH}
                                            call .venv${DEFAULT_PYTHON_VERSION}/Scripts/activate
                                            poetry run poe docs
                                            "C:\\Program Files\\7-Zip\\7z.exe" a -r docs.zip -w _docs -mem=AES256
                                            XCOPY docs.zip ${env.WORKSPACE}
                                        """
                                        stash includes: 'docs.zip', name: 'docs'
                                    }
                                }
                                stage("Run unit tests") {
                                    steps {
                                        script {
                                            def pythonVersions = RUN_PYTHON_VERSIONS.split(',')
                                            pythonVersions.each { version ->
                                                bat """
                                                    cd ${WIN_DOCKER_TMP_PATH}
                                                    call .venv${version}/Scripts/activate
                                                    poetry run poe tests --import-mode=importlib --cov=ingeniamotion --junitxml=pytest_reports/junit-tests-${version}.xml --junit-prefix=${version} -m "not ethernet and not soem and not fsoe and not fsoe_phase2 and not canopen and not virtual and not soem_multislave and not skip_testing_framework"
                                                """
                                            }
                                        }
                                    }
                                    post {
                                        always {
                                            bat """
                                                mkdir -p pytest_reports
                                                XCOPY ${WIN_DOCKER_TMP_PATH}\\pytest_reports\\* pytest_reports\\ /s /i /y /e /h
                                                move ${WIN_DOCKER_TMP_PATH}\\.coverage .coverage_unit_tests
                                            """
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
                                        script {
                                            def pythonVersions = RUN_PYTHON_VERSIONS.split(',')
                                            pythonVersions.each { version ->
                                                bat """
                                                    cd ${WIN_DOCKER_TMP_PATH}
                                                    call .venv${version}/Scripts/activate
                                                    poetry run poe tests --import-mode=importlib --cov=ingeniamotion --junitxml=pytest_reports/junit-tests-${version}.xml --junit-prefix=${version} -m virtual --setup summit_testing_framework.setups.virtual_drive.TESTS_SETUP
                                                """
                                            }
                                        }
                                    }
                                    post {
                                        always {
                                            bat """
                                                mkdir -p pytest_reports
                                                XCOPY ${WIN_DOCKER_TMP_PATH}\\pytest_reports\\* pytest_reports\\ /s /i /y /e /h
                                                move ${WIN_DOCKER_TMP_PATH}\\.coverage .coverage_virtual
                                            """
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
                                publishDistExt("_docs", DISTEXT_PROJECT_DIR, true)
                            }
                        }
                        stage('Publish wheels') {
                            agent {
                                docker {
                                    label 'worker'
                                    image "ingeniacontainers.azurecr.io/publisher:dev"
                                }
                            }
                            stages {
                                stage('Unstash build') {
                                    steps {
                                        unstash 'build'
                                    }
                                }
                                stage('Publish Novanta PyPi') {
                                    steps {
                                        publishNovantaPyPi('dist/*')
                                    }
                                }
                                stage('Publish PyPi') {
                                    when {
                                        branch 'master'
                                    }
                                    steps {
                                        publishPyPi('dist/*')
                                    }
                                }
                            }
                        }
                    }
                }

                stage('HW Tests CanOpen and Ethernet') {
                    when {
                        beforeOptions true
                        beforeAgent true
                        expression {
                          [
                            "canopen_everest",
                            "canopen_everest_no_framework",
                            "canopen_capitan",
                            "canopen_capitan_no_framework",
                            "ethernet_everest",
                            "ethernet_capitan"
                          ].any { it ==~ params.run_test_stages }
                        }
                    }
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
                        stage('Create virtual environments') {
                            steps {
                                script {
                                    createVirtualEnvironments()
                                }
                            }
                        }
                        stage("CanOpen Everest") {
                            when {
                                expression {
                                    "canopen_everest" ==~ params.run_test_stages
                                }
                            }
                            steps {
                                runTestHW("canopen_everest", "canopen and not skip_testing_framework", "CAN_EVE_SETUP")
                            }
                        }
                        stage("CanOpen Everest (skip_testing_framework)") {
                            when {
                                expression {
                                    "canopen_everest_no_framework" ==~ params.run_test_stages
                                }
                            }
                            steps {
                                runTestHW("canopen_everest_no_framework", "canopen and skip_testing_framework", "CAN_EVE_SETUP")
                            }
                        }
                        stage("Ethernet Everest") {
                            when {
                                expression {
                                    "ethernet_everest" ==~ params.run_test_stages
                                }
                            }
                            steps {
                                runTestHW("ethernet_everest", "ethernet", "ETH_EVE_SETUP", USE_WIRESHARK_LOGGING)
                            }
                        }
                        stage("CanOpen Capitan") {
                            when {
                                expression {
                                    "canopen_capitan" ==~ params.run_test_stages
                                }
                            }
                            steps {
                                runTestHW("canopen_capitan", "canopen and not skip_testing_framework", "CAN_CAP_SETUP")
                            }
                        }
                        stage("CanOpen Capitan (skip_testing_framework)") {
                            when {
                                expression {
                                    "canopen_capitan_no_framework" ==~ params.run_test_stages
                                }
                            }
                            steps {
                                runTestHW("canopen_capitan_no_framework", "canopen and skip_testing_framework", "CAN_EVE_SETUP")
                            }
                        }
                        stage("Ethernet Capitan") {
                            when {
                                // Remove this after fixing INGK-982
                                expression { false }
                            }
                            steps {
                                runTestHW("ethernet_capitan", "ethernet", "ETH_CAP_SETUP", USE_WIRESHARK_LOGGING)
                            }
                        }
                    }
                }
                stage('Hw Tests Ethercat') {
                    when {
                        beforeOptions true
                        beforeAgent true
                        expression {
                          [
                            "ethercat",
                            "ethercat_everest",
                            "ethercat_everest_no_framework",
                            "ethercat_capitan",
                            "ethercat_capitan_no_framework",
                            "ethercat_multislave",
                            "fsoe_phase1",
                            "fsoe_phase1_no_framework",
                            "fsoe_phase2",
                            "fsoe_phase2_no_framework"
                          ].any { it ==~ params.run_test_stages }
                        }
                    }
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
                        stage('Create virtual environments') {
                            steps {
                                script {
                                    createVirtualEnvironments()
                                }
                            }
                        }
                        stage("Ethercat Everest") {
                            when {
                                // Remove this after fixing INGK-983
                                expression { false }
                            }
                            steps {
                                runTestHW("ethercat_everest", "soem and not skip_testing_framework", "ECAT_EVE_SETUP", USE_WIRESHARK_LOGGING)
                            }
                        }
                        stage("Ethercat Everest (skip_testing_framework)") {
                            when {
                                // Remove this after fixing INGK-983
                                expression { false }
                            }
                            steps {
                                runTestHW("ethercat_everest_no_framework", "soem and not skip_testing_framework", "ECAT_EVE_SETUP", USE_WIRESHARK_LOGGING)
                            }
                        }
                        stage("Ethercat Capitan") {
                            when {
                                expression {
                                    "ethercat_capitan" ==~ params.run_test_stages
                                }
                            }
                            steps {
                                runTestHW("ethercat_capitan", "soem and not skip_testing_framework", "ECAT_CAP_SETUP", USE_WIRESHARK_LOGGING)
                            }
                        }
                        stage("Ethercat Capitan (skip_testing_framework)") {
                            when {
                                expression {
                                    "ethercat_capitan_no_framework" ==~ params.run_test_stages
                                }
                            }
                            steps {
                                runTestHW("ethercat_capitan_no_framework", "soem and skip_testing_framework", "ECAT_CAP_SETUP", USE_WIRESHARK_LOGGING)
                            }
                        }
                        stage("Safety Denali Phase I") {
                            when {
                                expression {
                                    "fsoe_phase1" ==~ params.run_test_stages
                                }
                            }
                            steps {
                                runTestHW("fsoe_phase1", "fsoe and not skip_testing_framework", "ECAT_DEN_S_PHASE1_SETUP", USE_WIRESHARK_LOGGING)
                            }
                        }
                        stage("Safety Denali Phase I (skip_testing_framework)") {
                            when {
                                expression {
                                    "fsoe_phase1_no_framework" ==~ params.run_test_stages
                                }
                            }
                            steps {
                                runTestHW("fsoe_phase1_no_framework", "fsoe and skip_testing_framework", "ECAT_DEN_S_PHASE1_SETUP", USE_WIRESHARK_LOGGING)
                            }
                        }
                        stage("Safety Denali Phase II") {
                            when {
                                expression {
                                    "fsoe_phase2" ==~ params.run_test_stages
                                }
                            }
                            steps {
                                runTestHW("fsoe_phase2", "(fsoe or fsoe_phase2) and not skip_testing_framework", "ECAT_DEN_S_PHASE2_SETUP", USE_WIRESHARK_LOGGING)
                            }
                        }
                        stage("Safety Denali Phase II (skip_testing_framework)") {
                            when {
                                expression {
                                    "fsoe_phase2_no_framework" ==~ params.run_test_stages
                                }
                            }
                            steps {
                                runTestHW("fsoe_phase2_no_framework", "(fsoe or fsoe_phase2) and skip_testing_framework", "ECAT_DEN_S_PHASE2_SETUP", USE_WIRESHARK_LOGGING)
                            }
                        }
                        stage("Ethercat Multislave") {
                            when {
                                expression {
                                    "ethercat_multislave" ==~ params.run_test_stages
                                }
                            }
                            steps {
                                runTestHW("ethercat_multislave", "soem_multislave", "ECAT_MULTISLAVE_SETUP", USE_WIRESHARK_LOGGING)
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
                    bat "XCOPY ${env.WORKSPACE} ${WIN_DOCKER_TMP_PATH} /s /i /y /e /h"
                    createVirtualEnvironments(WIN_DOCKER_TMP_PATH, DEFAULT_PYTHON_VERSION)
                    bat """
                        cd ${WIN_DOCKER_TMP_PATH}
                        call .venv${DEFAULT_PYTHON_VERSION}/Scripts/activate
                        poetry run poe cov-combine --${coverage_files}
                        poetry run poe cov-report
                        XCOPY coverage.xml ${env.WORKSPACE}
                    """
                }
                recordCoverage(tools: [[parser: 'COBERTURA', pattern: 'coverage.xml']])
                archiveArtifacts artifacts: '*.xml'
            }
        }
    }
}
