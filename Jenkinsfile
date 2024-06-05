@Library('cicd-lib@0.11') _

def SW_NODE = "windows-slave"
def ECAT_NODE = "ecat-test"
def ECAT_NODE_LOCK = "test_execution_lock_ecat"
def CAN_NODE = "canopen-test"
def CAN_NODE_LOCK = "test_execution_lock_can"

def DOCKER_IMAGE = "ingeniacontainers.azurecr.io/win-python-builder:1.4"

def DEFAULT_TOX_PYTHON_VERSION = "39"
def DEFAULT_PYTHON_VERSION = "3.9"
def TOX_VERSION = "4.12.1"

def SMOKE_TESTS_FLAG = ""

def BRANCH_NAME_MASTER = "master"
def DISTEXT_PROJECT_DIR = "doc/ingeniamotion"

def dockerInstallTox = {
    bat """
        py -${DEFAULT_PYTHON_VERSION} -m pip install tox==${TOX_VERSION}
    """
}

def installTox = {
    bat """
        py -${DEFAULT_PYTHON_VERSION} -m venv venv
        venv\\Scripts\\python.exe -m pip install tox==${TOX_VERSION}
    """
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
        stage('Run tests on Linux') {
            agent {
                docker {
                    label "worker"
                    image "ingeniacontainers.azurecr.io/docker-python:1.4"
                }
            }
            stages {
                stage('Install deps') {
                    steps {
                        sh """
                            python${DEFAULT_PYTHON_VERSION} -m pip install tox==${TOX_VERSION}
                        """
                    }
                }
                stage('Run no-connection tests') {
                    steps {
                        sh """
                            python${DEFAULT_PYTHON_VERSION} -m tox -e py${DEFAULT_TOX_PYTHON_VERSION} -- -m virtual --protocol virtual --junitxml=pytest_virtual_report.xml
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
                    image DOCKER_IMAGE
                }
            }
            stages {
                stage('Install deps') {
                    steps {
                        script {dockerInstallTox ()}
                    }
                }
                stage('Build wheels') {
                    steps {
                        bat """
                             tox -e build
                        """
                    }
                }
                stage('Make a static type analysis') {
                    steps {
                        bat """
                            tox -e type
                        """
                    }
                }
                stage('Check formatting') {
                    steps {
                        bat """
                            tox -e format
                        """
                    }
                }
                stage('Generate documentation') {
                    steps {
                        bat """
                            tox -e docs
                        """
                    }
                }
                stage("Run virtual drive tests") {
                    environment {
                        GIT_SSH_COMMAND = 'ssh -i C:/id_rsa -o StrictHostKeyChecking=no'
                    }
                    steps {
                        withCredentials([sshUserPrivateKey(credentialsId: 'Bitbucket SSH', keyFileVariable: 'KEY')]) {
                            bat """
                                COPY %KEY% C:\\id_rsa
                                tox -e virtual -- --junitxml=pytest_reports\\pytest_virtual_report.xml
                            """
                        }
                    }
                    post {
                        always {
                            bat """
                                move .coverage .coverage_virtual
                            """    
                            junit "pytest_reports\\pytest_virtual_report.xml"
                            stash includes: '.coverage_virtual', name: 'coverage_report_virtual'
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
        stage('Ecat tests') {
            options {
                lock(ECAT_NODE_LOCK)
            }
            agent {
                label ECAT_NODE
            }
            stages {
                stage("Checkout") {
                    steps {
                        checkout scm
                        script {installTox ()}
                    }
                }
                stage("Load FW") {
                    steps {
                        bat """
                                venv\\Scripts\\python.exe -m tox -e firmware -- soem
                            """
                    }   
                }
                stage('Run tests') {
                    matrix {
                        axes {
                            axis {
                                name 'SLAVE'
                                values '0', '1'
                            }
                            axis {
                                name 'PYTHON'
                                values '39', '310', '311', '312'
                            }
                        }
                        excludes {
                            // Remove this exclude after fixing INGM-376
                            exclude {
                                axis {
                                    name 'SLAVE'
                                    values '0'
                                }
                            }
                        }
                        stages {
                            stage('Set env to run only smoke tests') {
                                when {
                                    allOf{
                                        not{ branch 'master' };
                                        not{ branch 'develop' };
                                        expression { params.TESTS == 'Smoke' }
                                    }
                                }
                                steps {
                                    script {
                                        SMOKE_TESTS_FLAG = "-m smoke"
                                    }
                                }
                            }
                            stage('Set env to run all tests') {
                                when {
                                    anyOf{
                                        branch 'master';
                                        branch 'develop';
                                        expression { params.TESTS == 'All' }
                                    }
                                }
                                steps {
                                    script {
                                        SMOKE_TESTS_FLAG = ""
                                    }
                                }
                            }
                            stage('Run tests') {
                                options {
                                    lock('sequential-matrix')
                                }
                                when {
                                    anyOf{
                                        expression { SMOKE_TESTS_FLAG == "" };
                                        allOf {
                                            expression { SMOKE_TESTS_FLAG == "-m smoke" };
                                            expression { PYTHON == DEFAULT_TOX_PYTHON_VERSION }
                                        }
                                    }
                                }
                                steps {
                                    bat """
                                        venv\\Scripts\\python.exe -m tox -e py${PYTHON} -- ${SMOKE_TESTS_FLAG} --protocol soem --slave ${SLAVE} --junitxml=pytest_reports/pytest_soem_${SLAVE}_report_py${PYTHON}.xml
                                    """
                                }
                                post {
                                    always {
                                        bat """
                                            move .coverage .coverage_soem
                                        """    
                                        junit "pytest_reports\\*.xml"
                                        archiveArtifacts artifacts: 'pytest_reports\\*.xml'
                                        stash includes: ".coverage_soem", name: "coverage_report_soem"
                                    }
                                }
                            }
                        }
                    }          
                }
            }
        }
        stage('Canopen and ethernet tests') {
            options {
                lock(CAN_NODE_LOCK)
            }
            agent {
                label CAN_NODE
            }
            stages {
                stage("Checkout") {
                    steps {
                        checkout scm
                        script {installTox ()}
                    }
                }
                stage("Load FW") {
                    steps {
                        bat """
                                venv\\Scripts\\python.exe -m tox -e firmware -- canopen
                            """
                    }   
                }
                stage('Run tests') {
                    matrix {
                        axes {
                            axis {
                                name 'PROTOCOL'
                                values 'canopen', 'eoe'
                            }
                            axis {
                                name 'SLAVE'
                                values '0', '1'
                            }
                            axis {
                                name 'PYTHON'
                                values '39', '310', '311', '312'
                            }
                        }
                        excludes {
                            // Remove this exclude after fixing CAP-924
                            exclude {
                                axis {
                                    name 'PROTOCOL'
                                    values 'eoe'
                                }
                                axis {
                                    name 'SLAVE'
                                    values '1'
                                }
                            }
                        }
                        stages {
                            stage('Set env to run only smoke tests') {
                                when {
                                    allOf{
                                        not{ branch 'master' };
                                        not{ branch 'develop' };
                                        expression { params.TESTS == 'Smoke' }
                                    }
                                }
                                steps {
                                    script {
                                        SMOKE_TESTS_FLAG = "-m smoke"
                                    }
                                }
                            }
                            stage('Set env to run all tests') {
                                when {
                                    anyOf{
                                        branch 'master';
                                        branch 'develop';
                                        expression { params.TESTS == 'All' }
                                    }
                                }
                                steps {
                                    script {
                                        SMOKE_TESTS_FLAG = ""
                                    }
                                }
                            }
                            stage('Run tests') {
                                options {
                                    lock('sequential-matrix')
                                }
                                when {
                                    anyOf{
                                        expression { SMOKE_TESTS_FLAG == "" };
                                        allOf {
                                            expression { SMOKE_TESTS_FLAG == "-m smoke" };
                                            expression { PYTHON == DEFAULT_TOX_PYTHON_VERSION }
                                        }
                                    }
                                }
                                steps {
                                    bat """
                                        venv\\Scripts\\python.exe -m tox -e py${PYTHON} -- ${SMOKE_TESTS_FLAG} --protocol ${PROTOCOL} --slave ${SLAVE} --junitxml=pytest_reports/pytest_${PROTOCOL}_${SLAVE}_report_py${PYTHON}.xml
                                    """
                                }
                                post {
                                    always {
                                        bat """
                                            move .coverage .coverage_${PROTOCOL}
                                        """    
                                        junit "pytest_reports\\pytest_${PROTOCOL}_${SLAVE}_report_py${PYTHON}.xml"
                                        archiveArtifacts artifacts: "pytest_reports\\pytest_${PROTOCOL}_${SLAVE}_report_py${PYTHON}.xml"
                                        stash includes: ".coverage_${PROTOCOL}", name: "coverage_report_${PROTOCOL}"
                                    }
                                }
                            }
                        }
                    }          
                }
            }
        }
        stage('Publish coverage') {
            // TODO: Remove when condition when INGM-395 is fixed 
            when {
                beforeAgent true
                expression { false }
            }
            agent {
                docker {
                    label SW_NODE
                    image DOCKER_IMAGE
                }
            }
            stages {
                stage('Install deps') {
                    steps {
                        script {dockerInstallTox ()}
                    }
                }
                stage('Publish coverage') {
                    steps {
                        unstash 'coverage_report_virtual'
                        unstash 'coverage_report_eoe'
                        unstash 'coverage_report_canopen'
                        unstash 'coverage_report_soem'
 
                        bat """
                            py -${DEFAULT_PYTHON_VERSION} -m tox -e coverage -- .coverage_eoe .coverage_canopen .coverage_virtual .coverage_soem
                        """

                        publishCoverage adapters: [coberturaReportAdapter('coverage.xml')]
                        archiveArtifacts artifacts: '*.xml'
                    }
                }
            }
        }
        stage('Publish ingeniamotion'){
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
    }
}