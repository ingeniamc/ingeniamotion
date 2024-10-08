@Library('cicd-lib@0.11') _

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
def PYTHON_VERSION_MIN = "py39"
def PYTHON_VERSION_MAX = "py312"

SMOKE_TESTS_FLAG = ""

def BRANCH_NAME_MASTER = "master"
def DISTEXT_PROJECT_DIR = "doc/ingeniamotion"

coverage_stashes = []

def runTestHW(protocol, slave) {
    try {
        bat "py -${DEFAULT_PYTHON_VERSION} -m tox -e ${RUN_PYTHON_VERSIONS} -- " +
                "${SMOKE_TESTS_FLAG} " +
                "--protocol ${protocol} " +
                "--slave ${slave} " +
                "--junitxml=pytest_reports/pytest_${protocol}_${slave}_report_py.xml"
    } catch (err) {
        unstable(message: "Tests failed")
    } finally {
        coverage_stash = ".coverage_${protocol}_${slave}"
        bat "move .coverage ${coverage_stash}"
        junit "pytest_reports\\pytest_${protocol}_${slave}_report_py.xml"
        stash includes: coverage_stash, name: coverage_stash
        coverage_stashes.add(coverage_stash)
    }
}

pipeline {
    agent none
    parameters {
        choice(
                choices: ['Smoke', 'All'],
                name: 'TESTS'
        )
    }
    stages {
        stage("Set env") {
            steps {
                script {
                    if (env.BRANCH_NAME == 'master') {
                        RUN_PYTHON_VERSIONS = ALL_PYTHON_VERSIONS
                        SMOKE_TESTS_FLAG = ""
                    } else if (env.BRANCH_NAME == 'develop') {
                        RUN_PYTHON_VERSIONS = ALL_PYTHON_VERSIONS
                        SMOKE_TESTS_FLAG = ""
                    } else if (env.BRANCH_NAME.startsWith('release/')) {
                        RUN_PYTHON_VERSIONS = ALL_PYTHON_VERSIONS
                        SMOKE_TESTS_FLAG = ""
                    } else {
                        RUN_PYTHON_VERSIONS = "${PYTHON_VERSION_MIN},${PYTHON_VERSION_MAX}"
                        if (params.TESTS == 'Smoke') {
                            SMOKE_TESTS_FLAG = "-m smoke"
                        }
                    }
                }
            }
        }

        stage('Run tests on Linux') {
            agent {
                docker {
                    label "worker"
                    image LIN_DOCKER_IMAGE
                }
            }
            stages {
                stage('Run no-connection tests') {
                    steps {
                        sh """
                            python${DEFAULT_PYTHON_VERSION} -m tox -e ${RUN_PYTHON_VERSIONS} -- -m virtual --protocol virtual --junitxml=pytest_virtual_report.xml
                        """
                    }
                    post {
                        always {
                            junit "pytest_virtual_report.xml"
                        }
                    }
                }
            }
        }
        stage('Build wheels and documentation') {
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
                    }
                }
                stage("Run virtual drive tests") {
                    steps {
                        bat "py -${DEFAULT_PYTHON_VERSION} -m tox -e ${RUN_PYTHON_VERSIONS} -- -m" +
                                " virtual --protocol virtual " +
                                "--junitxml=pytest_reports\\pytest_virtual_report.xml"
                    }
                    post {
                        always {
                            bat "move .coverage .coverage_virtual"
                            junit "pytest_reports\\pytest_virtual_report.xml"
                            stash includes: '.coverage_virtual', name: '.coverage_virtual'
                            script {
                                coverage_stashes.add(".coverage_virtual")
                            }
                        }
                    }
                }
                stage('Archive') {
                    steps {
                        bat """
                            "C:\\Program Files\\7-Zip\\7z.exe" a -r docs.zip -w _docs -mem=AES256
                        """
                        stash includes: 'dist\\*, docs.zip', name: 'publish_files'
                        archiveArtifacts artifacts: "dist\\*, docs.zip"
                    }
                }
            }
        }
        stage('Publish ingeniamotion') {
            when {
                beforeAgent true
                branch BRANCH_NAME_MASTER
            }
            agent {
                docker {
                    label "worker"
                    image "ingeniacontainers.azurecr.io/publisher:1.8"
                }
            }
            steps {
                unstash 'publish_files'
                unzip zipFile: 'docs.zip', dir: '.'
                publishDistExt("_docs", DISTEXT_PROJECT_DIR, false)
                publishPyPi("dist/*")
            }
        }

        stage('Run tests with HW') {
            parallel {
                stage('CanOpen and Ethernet') {
                    options {
                        lock(CAN_NODE_LOCK)
                    }
                    agent {
                        label CAN_NODE
                    }
                    stages {
                        stage("Canopen - Slave 0") {
                            steps {
                                runTestHW("canopen", 0)
                            }
                        }
                        stage("Ethernet - Slave 0") {
                            steps {
                                runTestHW("eoe", 0)
                            }
                        }
                        stage("Canopen - Slave 1") {
                            steps {
                                runTestHW("canopen", 1)
                            }
                        }
                        stage("Ethernet - Slave 1") {
                            when {
                                // Remove this after fixing CAP-924
                                expression { false }
                            }
                            steps {
                                runTestHW("eoe", 1)
                            }
                        }
                    }
                }
                stage('Ethercat') {
                    options {
                        lock(ECAT_NODE_LOCK)
                    }
                    agent {
                        label ECAT_NODE
                    }
                    stages {
                        stage("Ethercat - Slave 0") {
                            when {
                                // Remove this after fixing INGM-376
                                expression { false }
                            }
                            steps {
                                runTestHW("soem", 0)
                            }
                        }
                        stage("Ethercat - Slave 1") {
                            steps {
                                runTestHW("soem", 1)
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
