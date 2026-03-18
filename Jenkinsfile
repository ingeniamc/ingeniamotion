@Library('cicd-lib@0.20') _

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

def runTest(run_identifier, markers, setup_name, extra_args = "", useWireshark = false, workingDir = null) {
    def withWiresharkEnv = useWireshark
    // Automatically add USE_WIRESHARK_LOGGING to extra_args when useWireshark is true
    def effectiveExtraArgs = useWireshark ? "${USE_WIRESHARK_LOGGING} ${extra_args}".trim() : extra_args
    try {
        timeout(time: 1, unit: 'HOURS') {
            def pythonVersions = RUN_PYTHON_VERSIONS.split(',')
            pythonVersions.each { version ->
                def envVars = withWiresharkEnv ? 
                    ["WIRESHARK_SCOPE=${params.WIRESHARK_LOGGING_SCOPE}", "CLEAR_WIRESHARK_LOG_IF_SUCCESSFUL=${params.CLEAR_SUCCESSFUL_WIRESHARK_LOGS}", "START_WIRESHARK_TIMEOUT_S=${START_WIRESHARK_TIMEOUT_S}"] : 
                    []
                
                withEnv(envVars) {
                    try {
                        def cdCmd = workingDir ? "cd ${workingDir}" : ""
                        def testArgs = [
                            "--import-mode=importlib",
                            "--cov=ingeniamotion",
                            "--junitxml=pytest_reports/junit-tests-${version}.xml",
                            "--junit-prefix=${version}",
                            "-m \"${markers}\"",
                            "--setup ${setup_name}",
                            "--job_name=\"${env.JOB_NAME}-#${env.BUILD_NUMBER}-${run_identifier}\"",
                            "--tb=long",
                            "-o log_cli=True",
                            "--enable_firmware_version_check",
                            effectiveExtraArgs
                        ].findAll { it }.join(" ")
                        
                        if (isUnix()) {
                            sh """
                                ${cdCmd}
                                . .venv${version}/bin/activate
                                poetry run poe tests ${testArgs}
                                deactivate
                            """
                        } else {
                            bat """
                                ${cdCmd}
                                call .venv${version}/Scripts/activate
                                poetry run poe tests ${testArgs}
                                deactivate
                            """
                        }
                    } catch (err) {
                        unstable(message: "Tests failed")
                    } finally {
                        // Handle junit reports and coverage
                        if (workingDir && isUnix()) {
                            sh """
                                mkdir -p pytest_reports
                                cp ${workingDir}/pytest_reports/* pytest_reports/ 2>/dev/null || true
                            """
                        } else if (workingDir && !isUnix()) {
                            bat """
                                mkdir -p pytest_reports
                                XCOPY ${workingDir}\\pytest_reports\\* pytest_reports\\ /s /i /y /e /h 2>nul || exit /b 0
                            """
                        }
                        
                        junit "pytest_reports\\*.xml"
                        
                        // Delete the junit after publishing it so it not re-published on the next stage
                        if (isUnix()) {
                            sh "rm -f pytest_reports/*.xml"
                        } else {
                            bat "del /S /Q pytest_reports\\*.xml"
                        }
                        
                        // Save the coverage so it can be unified and published later
                        def coverage_stash = ".coverage_${run_identifier}_${version}"
                        
                        if (isUnix()) {
                            if (workingDir) {
                                sh "cp ${workingDir}/.coverage ${coverage_stash} 2>/dev/null || true"
                            } else {
                                sh "mv .coverage ${coverage_stash} 2>/dev/null || true"
                            }
                        } else {
                            if (workingDir) {
                                bat "move ${workingDir}\\.coverage ${coverage_stash} 2>nul || exit /b 0"
                            } else {
                                bat "move .coverage ${coverage_stash} 2>nul || exit /b 0"
                            }
                        }
                        
                        stash includes: coverage_stash, name: coverage_stash, allowEmpty: true
                        coverage_stashes.add(coverage_stash)
                    }
                }
            }
        }
    } finally {
        if (withWiresharkEnv) {
            archiveWiresharkLogs()
            clearWiresharkLogs()
        }
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
                            label "lin-worker"
                            image LIN_DOCKER_IMAGE
                            args '-u root:root'
                        }
                    }
                    stages {
                        stage('Check Dependencies') {
                            steps {
                                script {
                                    checkDependencies()
                                }
                            }
                        }
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
                                    runTest("virtual_linux", "virtual", "tests.setups.virtual_drive.VIRTUAL_DRIVE_ETHERNET_SETUP", "", false, LIN_DOCKER_TMP_PATH)
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
                                            runTest("unit_tests", "not ethernet and not soem and not fsoe and not fsoe_phase2 and not canopen and not virtual and not soem_multislave", "tests.setups.virtual_drive.VIRTUAL_DRIVE_ETHERNET_SETUP", "", false, WIN_DOCKER_TMP_PATH)
                                        }
                                    }
                                }
                                stage("Run virtual drive tests") {
                                    steps {
                                        script {
                                            runTest("virtual", "virtual", "tests.setups.virtual_drive.VIRTUAL_DRIVE_ETHERNET_SETUP", "", false, WIN_DOCKER_TMP_PATH)
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
                                label "lin-worker"
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
                                    label 'lin-worker'
                                    image "ingeniacontainers.azurecr.io/publisher:1.8"
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
                            "canopen_capitan",
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
                                runTest("canopen_everest", "canopen", "tests.setups.rack_specifiers.CAN_SETUP@EVE-XCR-C", "", false)
                            }
                        }
                        stage("Ethernet Everest") {
                            when {
                                expression {
                                    "ethernet_everest" ==~ params.run_test_stages
                                }
                            }
                            steps {
                                runTest("ethernet_everest", "ethernet", "tests.setups.rack_specifiers.ETH_SETUP@EVE-XCR-C", "", true)
                            }
                        }
                        stage("CanOpen Capitan") {
                            when {
                                expression {
                                    "canopen_capitan" ==~ params.run_test_stages
                                }
                            }
                            steps {
                                runTest("canopen_capitan", "canopen", "tests.setups.rack_specifiers.CAN_SETUP@CAP-XCR-C", "", false)
                            }
                        }
                        stage("Ethernet Capitan") {
                            when {
                                // Remove this after fixing INGK-982
                                expression { false }
                            }
                            steps {
                                runTest("ethernet_capitan", "ethernet", "tests.setups.rack_specifiers.ETH_SETUP@CAP-XCR-C", "", true)
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
                            "ethercat_capitan",
                            "ethercat_multislave",
                            "fsoe_phase1",
                            "fsoe_phase2",
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
                                runTest("ethercat_everest", "soem", "tests.setups.rack_specifiers.ECAT_SETUP@EVE-XCR-E", "", true)
                            }
                        }
                        stage("Ethercat Capitan") {
                            when {
                                expression {
                                    "ethercat_capitan" ==~ params.run_test_stages
                                }
                            }
                            steps {
                                runTest("ethercat_capitan", "soem", "tests.setups.rack_specifiers.ECAT_SETUP@CAP-XCR-E", "", true)
                            }
                        }
                        stage("Safety Denali Phase I") {
                            when {
                                expression {
                                    "fsoe_phase1" ==~ params.run_test_stages
                                }
                            }
                            steps {
                                runTest("fsoe_phase1", "fsoe", "tests.setups.rack_specifiers.ECAT_DEN_S_NET_E_SETUP@PHASE1", "", true)
                            }
                        }
                        stage("Safety Denali Phase II") {
                            when {
                                expression {
                                    "fsoe_phase2" ==~ params.run_test_stages
                                }
                            }
                            steps {
                                runTest("fsoe_phase2", "fsoe or fsoe_phase2", "tests.setups.rack_specifiers.ECAT_DEN_S_NET_E_SETUP@PHASE2", "", true)
                            }
                        }
                        stage("Ethercat Multislave") {
                            when {
                                expression {
                                    "ethercat_multislave" ==~ params.run_test_stages
                                }
                            }
                            steps {
                                runTest("ethercat_multislave", "soem_multislave", "tests.setups.rack_specifiers.ECAT_MULTISLAVE_SETUP", "", true)
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
