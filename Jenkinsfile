@Library('cicd-lib@cit-564-migration-to-cicdlib-and-migration-of-pipelines') _

import python.VirtualEnvironment
import python.VEnvManager
import pytest.TestSession
import pytest.TestGroup
import pytest.PyTestManager
import pytest.TestDashboardBuilder

def SW_NODE = "windows-slave"
def ECAT_NODE = "ecat-test"
def ECAT_NODE_LOCK = "test_execution_lock_ecat"
def CAN_NODE = "canopen-test"
def CAN_NODE_LOCK = "test_execution_lock_can"

def LIN_DOCKER_IMAGE = "ingeniacontainers.azurecr.io/docker-python:1.6"
def WIN_DOCKER_IMAGE = "ingeniacontainers.azurecr.io/win-python-builder:1.7"
def PUBLISHER_DOCKER_IMAGE = "ingeniacontainers.azurecr.io/publisher:1.8"

WIN_DOCKER_TMP_PATH = "C:\\Users\\ContainerAdministrator\\ingeniamotion"
LIN_DOCKER_TMP_PATH = "/tmp/ingeniamotion"

DEFAULT_PYTHON_VERSION = "3.9"

def ALL_PYTHON_VERSIONS = ["3.9", "3.10", "3.11", "3.12"] as Set
def PYTHON_VERSION_MIN = "3.9"
def PYTHON_VERSION_MAX = "3.12"

def BRANCH_NAME_MASTER = "master"
def DISTEXT_PROJECT_DIR = "doc/ingeniamotion"

/* List of markers that require hardware */
def HARDWARE_MARKERS = ["ethernet", "soem", "soem_multislave", "canopen", "fsoe", "fsoe_phase2"]

@groovy.transform.Field
List wheel_stashes = []

VEnvManager venvManager = new VEnvManager(
    pipeline: this,
    default_python_version: DEFAULT_PYTHON_VERSION,
    poetry_default_install_command: "poetry sync --all-groups"
)

PyTestManager testManager = new PyTestManager(pipeline: this, venvManager: venvManager)

/* Define default base test sessions to be used/overridden in stages */
TestSession TEST_SESSIONS = new TestSession(
    covPackageName: "ingeniamotion",
    wiresharkScope: null, // Set later based on parameter
    wiresharkDir: "wireshark",
    startWiresharkTimeoutS: 10.0,
    importMode: "importlib",
    logCli: true,
    enableFirmwareVersionCheck: true,
)
TestSession HW_TEST_SESSIONS = TEST_SESSIONS.override()
TestGroup CAN_TESTS = testManager.createGroup("CAN_TEST_SESSIONS", HW_TEST_SESSIONS.override())
TestGroup ETH_TESTS = testManager.createGroup("ETH_TEST_SESSIONS", HW_TEST_SESSIONS.override())
TestGroup ECAT_TESTS = testManager.createGroup("ECAT_TEST_SESSIONS", HW_TEST_SESSIONS.override())
TestGroup LINUX_DOCKER_TESTS = testManager.createGroup("LINUX_DOCKER_TEST_SESSIONS", TEST_SESSIONS.override())
TestGroup WIN_DOCKER_TESTS = testManager.createGroup("WIN_DOCKER_TEST_SESSIONS", TEST_SESSIONS.override())

def reassignFilePermissions() {
    if (isUnix()) {
        sh 'chmod -R 777 .'
    }
}

/* Build develop everyday 3 times starting at 19:00 UTC (21:00 Barcelona Time), running all python versions */
CRON_SETTINGS = BRANCH_NAME == "develop" ? "0 19,21,23 * * * % PYTHON_VERSIONS=All;WIRESHARK_LOGGING=true" : ""

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
                'virtual_.*',
                'unit_.*',
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
            name: 'test_session_filter',
            description: 'Regex pattern for which test sessions to run (e.g. "fsoe_.*", "ethercat_everest", ".*" for all)'
        )
        booleanParam(name: 'WIRESHARK_LOGGING', defaultValue: false, description: 'Enable Wireshark logging')
        choice(
                choices: ['function', 'module', 'session'],
                name: 'WIRESHARK_LOGGING_SCOPE'
        )
        booleanParam(name: 'CLEAR_SUCCESSFUL_WIRESHARK_LOGS', defaultValue: true, description: 'Clears Wireshark logs if the test passed')
    }
    stages {
        stage('Prepare test sessions') {
            agent {
                docker {
                    label 'lin-worker'
                    image LIN_DOCKER_IMAGE
                    args '-u root:root'
                }
            }
            environment {
                VENV_WORKING_FOLDER = "${LIN_DOCKER_TMP_PATH}"
            }
            steps {
                script {
                    // Determine which Python versions to run tests against based on branch and parameters
                    Set pythonVersions
                    if (env.BRANCH_NAME == 'master') {
                        pythonVersions = ALL_PYTHON_VERSIONS
                    } else if (env.BRANCH_NAME.startsWith('release/')) {
                        pythonVersions = ALL_PYTHON_VERSIONS
                    } else {
                        if (env.PYTHON_VERSIONS == "MIN_MAX") {
                            pythonVersions = [PYTHON_VERSION_MIN, PYTHON_VERSION_MAX] as Set
                        } else if (env.PYTHON_VERSIONS == "MIN") {
                            pythonVersions = [PYTHON_VERSION_MIN] as Set
                        } else if (env.PYTHON_VERSIONS == "MAX") {
                            pythonVersions = [PYTHON_VERSION_MAX] as Set
                        } else if (env.PYTHON_VERSIONS == "All") {
                            pythonVersions = ALL_PYTHON_VERSIONS
                        } else { // Branch-indexing
                            pythonVersions = [PYTHON_VERSION_MIN] as Set
                        }
                    }

                    // Set dynamic properties according to job and parameters
                    TEST_SESSIONS.setAttributeInCascade(
                        runInVirtualEnvs: venvManager.pythonVersionsToDefaultVenvNames(pythonVersions),
                        jobName: "${env.JOB_NAME}-#${env.BUILD_NUMBER}",
                        wiresharkScope: params.WIRESHARK_LOGGING_SCOPE,
                        clearSuccessfulWiresharkLogs: params.CLEAR_SUCCESSFUL_WIRESHARK_LOGS,
                    )

                    // Configure if ECAT and ETH sessions use Wireshark logging based on parameter
                    ECAT_TESTS.baseTestSession.setAttributeInCascade(
                        useWiresharkLogging: params.WIRESHARK_LOGGING,
                    )
                    ETH_TESTS.baseTestSession.setAttributeInCascade(
                        useWiresharkLogging: params.WIRESHARK_LOGGING,
                    )

                    testManager.testSessionFilter = params.test_session_filter

                    echo("Test sessions have been configured to run with the following base configuration:\n${TEST_SESSIONS.configSummary()}")

                    // Create a minimal virtual environment for specifier export and test collection
                    venvManager.copyToWorkingFolder()
                    venvManager.createPoetryEnvironment()

                    // Export specifiers and populate TestGroup sessions (policy + uid-regex evaluated here).
                    testManager.buildTestSessions("tests.setups.rack_specifiers")
                    testManager.buildTestSessions("tests.setups.virtual_drive")

                    // Register manual test sessions
                    WIN_DOCKER_TESTS.addSession(
                        uid: "unit_tests",
                        markers: PyTestManager.markersExcludeString(HARDWARE_MARKERS + ["virtual"]),
                        stageName: "Unit Tests (Windows)")

                    testManager.echoTestGroupsSummary()
                    testManager.generateTestDashboard()
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
                    parallel {
                        stage('Build Windows') {
                            agent {
                                docker {
                                    label SW_NODE
                                    image WIN_DOCKER_IMAGE
                                }
                            }
                            environment {
                                VENV_WORKING_FOLDER = "${WIN_DOCKER_TMP_PATH}"
                            }
                            stages {
                                stage('Move workspace') {
                                    steps {
                                        script {
                                            venvManager.copyToWorkingFolder()
                                        }
                                    }
                                }
                                stage('Create virtual environments') {
                                    steps {
                                        script {
                                            venvManager.createPoetryEnvironments(
                                                pythonVersions: ALL_PYTHON_VERSIONS,
                                                installCommand: "poetry sync --all-groups --extras fsoe"
                                            )
                                        }
                                    }
                                }
                                stage('Build wheels') {
                                    steps {
                                        script {
                                            venvManager.withPython(DEFAULT_PYTHON_VERSION) { venv ->
                                                venv.run("poetry run poe build")
                                            }
                                            venvManager.copyFromWorkingFolder("dist/")
                                        }
                                        archiveArtifacts(artifacts: "dist\\*", followSymlinks: false)
                                        script {
                                            def stash_name = "publish_wheels-windows"
                                            wheel_stashes.add(stash_name)
                                            stash includes: "dist\\*", name: stash_name
                                        }
                                    }
                                }
                                stage('Make a static type analysis') {
                                    steps {
                                        script {
                                            venvManager.withPython(DEFAULT_PYTHON_VERSION) { venv ->
                                                venv.run("poetry run poe type")
                                            }
                                        }
                                    }
                                }
                                stage('Check formatting') {
                                    steps {
                                        script {
                                            venvManager.withPython(DEFAULT_PYTHON_VERSION) { venv ->
                                                venv.run("poetry run poe format")
                                            }
                                        }
                                    }
                                }
                                stage('Generate documentation') {
                                    steps {
                                        script {
                                            venvManager.withPython(DEFAULT_PYTHON_VERSION) { venv ->
                                                venv.run("poetry run poe docs")
                                            }
                                            venvManager.runInWorkingFolder('"C:\\Program Files\\7-Zip\\7z.exe" a -r docs.zip -w _docs -mem=AES256')
                                            venvManager.copyFromWorkingFolder("docs.zip")
                                        }
                                        stash includes: 'docs.zip', name: 'docs'
                                    }
                                }
                                stage('Run Docker tests (Windows)') {
                                    when {
                                        expression {
                                            WIN_DOCKER_TESTS.anyShouldRun()
                                        }
                                    }
                                    steps {
                                        script {
                                            WIN_DOCKER_TESTS.runTestStages()
                                        }
                                    }
                                }
                            }
                        }
                        stage('Build Linux') {
                            agent {
                                docker {
                                    label 'lin-worker'
                                    image LIN_DOCKER_IMAGE
                                    args '-u root:root'
                                }
                            }
                            environment {
                                VENV_WORKING_FOLDER = "${LIN_DOCKER_TMP_PATH}"
                            }
                            stages {
                                stage('Move workspace') {
                                    steps {
                                        script {
                                            venvManager.copyToWorkingFolder()
                                        }
                                    }
                                }
                                stage('Create virtual environments') {
                                    steps {
                                        script {
                                            venvManager.createPoetryEnvironments(
                                                pythonVersions: venvManager.defaultVenvNamesToVersion(LINUX_DOCKER_TESTS.baseTestSession.runInVirtualEnvs)
                                            )
                                        }
                                    }
                                }
                                stage('Run Linux Docker tests') {
                                    when {
                                        expression { LINUX_DOCKER_TESTS.anyShouldRun() }
                                    }
                                    steps {
                                        script {
                                            LINUX_DOCKER_TESTS.runTestStages()
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
                    }
                }
                stage('Publish documentation') {
                    when {
                        beforeAgent true
                        branch BRANCH_NAME_MASTER
                    }
                    agent {
                        label 'lin-worker'
                    }
                    steps {
                        unstash 'docs'
                        unzip zipFile: 'docs.zip', dir: '.'
                        publishDistExt('_docs', DISTEXT_PROJECT_DIR, true)
                    }
                }
                stage('Publish wheels') {
                    agent {
                        docker {
                            label 'lin-worker'
                            image PUBLISHER_DOCKER_IMAGE
                        }
                    }
                    stages {
                        stage('Unstash') {
                            steps {
                                script {
                                    for (stash_name in wheel_stashes) {
                                        unstash stash_name
                                    }
                                }
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

        stage('Tests') {
            parallel {
                stage('EtherCAT - Tests') {
                    when {
                        beforeOptions true
                        beforeAgent true
                        expression {
                            ECAT_TESTS.anyShouldRun()
                        }
                    }
                    options {
                        lock(ECAT_NODE_LOCK)
                    }
                    agent {
                        label ECAT_NODE
                    }
                    stages {
                        stage('Create virtual environments') {
                            steps {
                                script {
                                    venvManager.createPoetryEnvironments(
                                        pythonVersions: venvManager.defaultVenvNamesToVersion(ECAT_TESTS.baseTestSession.runInVirtualEnvs),
                                        installCommand: "poetry sync --all-groups --extras fsoe"
                                    )
                                }
                            }
                        }
                        stage('Run EtherCAT Tests') {
                            steps {
                                script {
                                    ECAT_TESTS.runTestStages()
                                }
                            }
                        }
                    }
                }
                stage('CANopen/Ethernet - Tests') {
                    when {
                        beforeOptions true
                        beforeAgent true
                        expression {
                            CAN_TESTS.anyShouldRun() || ETH_TESTS.anyShouldRun()
                        }
                    }
                    options {
                        lock(CAN_NODE_LOCK)
                    }
                    agent {
                        label CAN_NODE
                    }
                    stages {
                        stage('Create virtual environments') {
                            steps {
                                script {
                                    venvManager.createPoetryEnvironments(
                                        pythonVersions: venvManager.defaultVenvNamesToVersion(HW_TEST_SESSIONS.runInVirtualEnvs),
                                        installCommand: "poetry sync --all-groups --extras fsoe"
                                    )
                                }
                            }
                        }
                        stage('Run CANopen/Ethernet Tests') {
                            steps {
                                script {
                                    CAN_TESTS.runTestStages()
                                    ETH_TESTS.runTestStages()
                                }
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
            when {
                expression { testManager.hasCoverageFiles() }
            }
            environment {
                VENV_WORKING_FOLDER = "${WIN_DOCKER_TMP_PATH}"
            }
            steps {
                script {
                    def coverage_files = testManager.getCoverageFiles().join(" ")
                    venvManager.copyToWorkingFolder()
                    venvManager.createPoetryEnvironment(
                        installCommand: "poetry sync --all-groups --extras fsoe"
                    )
                    venvManager.withPython(DEFAULT_PYTHON_VERSION) { venv ->
                        venv.run("poetry run poe cov-combine -- ${coverage_files}")
                        venv.run("poetry run poe cov-report")
                    }
                    venvManager.copyFromWorkingFolder("coverage.xml")
                    recordCoverage(tools: [[parser: 'COBERTURA', pattern: 'coverage.xml']])
                    archiveArtifacts artifacts: '*.xml'
                }
            }
        }
    }
}
