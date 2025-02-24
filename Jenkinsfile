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
def PYTHON_VERSION_MIN = "py39"
def PYTHON_VERSION_MAX = "py312"

RUN_ONLY_SMOKE_TESTS = false

def BRANCH_NAME_MASTER = "master"
def DISTEXT_PROJECT_DIR = "doc/ingeniamotion"

coverage_stashes = []

def escapeSpaces(String input) {
    return input.replaceAll(" ", "%20")
}

def runTestHW(markers, setup_name) {

    if (RUN_ONLY_SMOKE_TESTS) {
        markers = markers + " and smoke"
    }

    try {
        bat "py -${DEFAULT_PYTHON_VERSION} -m tox -e ${RUN_PYTHON_VERSIONS} -- " +
                "-m \"${markers}\" " +
                "--setup tests.setups.rack_setups.${setup_name} " +
                "--cov=ingeniamotion " +
                "--job_name=\"${env.JOB_NAME}-#${env.BUILD_NUMBER}-${setup_name}\""
    } catch (err) {
        unstable(message: "Tests failed")
    } finally {
        def coverage_stash = ".coverage_${setup_name}"
        bat "move .coverage ${coverage_stash}"
        junit "pytest_reports\\*.xml"
        // Delete the junit after publishing it so it not re-published on the next stage
        bat "del /S /Q pytest_reports\\*.xml"
        stash includes: coverage_stash, name: coverage_stash
        coverage_stashes.add(coverage_stash)
    }
}

/* Build develop everyday at 19:00 UTC (21:00 Barcelona Time), running all tests */
CRON_SETTINGS = BRANCH_NAME == "develop" ? '''0 19 * * * % TESTS=All''' : ""

pipeline {
    agent none
    triggers {
        parameterizedCron(CRON_SETTINGS)
    }
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
                        RUN_ONLY_SMOKE_TESTS = false
                    } else if (env.BRANCH_NAME == 'develop') {
                        RUN_PYTHON_VERSIONS = ALL_PYTHON_VERSIONS
                        RUN_ONLY_SMOKE_TESTS = false
                    } else if (env.BRANCH_NAME.startsWith('release/')) {
                        RUN_PYTHON_VERSIONS = ALL_PYTHON_VERSIONS
                        RUN_ONLY_SMOKE_TESTS = false
                    } else {
                        RUN_PYTHON_VERSIONS = "${PYTHON_VERSION_MIN},${PYTHON_VERSION_MAX}"
                        if (params.TESTS == 'Smoke') {
                            RUN_ONLY_SMOKE_TESTS = true
                        }
                    }
                }
            }
        }

        stage('Get Ingenialink Build Number') {
            steps {
                script {
                    def destDir = "ingenialink_wheels/"
                    def commitHash = 'e04221273edd2458bbc6f96cf1a83f06987d5bdd'
                    def sourceJobName = 'Novanta Motion - Ingenia - Git/ingenialink-python'
                    def sourceJob = Jenkins.instance.getItemByFullName(sourceJobName)

                    if (sourceJob && sourceJob instanceof org.jenkinsci.plugins.workflow.multibranch.WorkflowMultiBranchProject) {
                        def foundBuild = null
                        def foundBranch = null

                        sourceJob.getAllJobs().each { branchJob ->
                            def fullBranchName = sourceJob.fullName + '/' + branchJob.name
                            def branch = Jenkins.instance.getItemByFullName(fullBranchName)

                            if (branch) {
                                branch.builds.reverse().each { build ->  // Reverse to start from the latest build
                                    def changeSets = build.changeSets
                                    changeSets.each { changeSet ->
                                        changeSet.items.each { item ->
                                            if (item.commitId == commitHash) {
                                                foundBuild = build
                                                foundBranch = branch
                                                return false
                                            }
                                        }
                                    }
                                }
                            }
                        }

                        if (foundBuild) {
                            def buildNumber = foundBuild.number.toString()
                            def workspaceDir = foundBuild.getArtifactsDir().toString()
                            
                            echo "Found build number: ${buildNumber}"
                            echo "Workspace directory: ${workspaceDir}"

                            echo "Branch name: ${foundBranch}"
                            echo "Branch display name: ${foundBranch.displayName}"

                            echo "Artifacts in ${workspaceDir}:"
                            foundBuild.artifacts.each { artifact ->
                                echo artifact.fileName
                                echo artifact.relativePath
                                echo artifact.displayPath
                            }
                            env.BUILD_NUMBER_ENV = buildNumber
                            env.BRANCH = foundBranch.toString()
                            env.WORKSPACE_DIR_ENV = workspaceDir
                        } else {
                            error "No build found for commit hash: ${commitHash}"
                        }
                    } else {
                        error "No job found with the name: ${sourceJobName} or it's not a multibranch project"
                    }
                    
                }
            }
        }

        // stage('Copy Artifacts Manually') {
        //     steps {
        //         script {
        //             def destDir = "ingenialink_wheels/"
        //             // def workspaceDir = escapeSpaces(env.WORKSPACE_DIR_ENV)
        //             def workspaceDir = env.WORKSPACE_DIR_ENV

        //             node {
        //                 sh """
        //                 mkdir -p ${destDir}
        //                 cp "${workspaceDir}/dist/ingenialink-7.4.1-cp39-cp39-win_amd64.whl" ${destDir}
        //                 cp "${workspaceDir}/dist_py312/ingenialink-7.4.1-cp312-cp312-win_amd64.whl" ${destDir}
        //                 """
        //             }
        //         }
        //     }
        // }

        stage('Copy Ingenialink Wheel Files') {
            agent any
            steps {
                script {
                    def destDir = "ingenialink_wheels"
                    def buildNumber = env.BUILD_NUMBER_ENV
                    def workspaceDir = env.WORKSPACE_DIR_ENV
                    def branch = env.BRANCH

                    if (buildNumber && branch) {
                        node {
                            copyArtifacts filter: '*.whl', fingerprintArtifacts: true, projectName: "${branch}", selector: specific(buildNumber)
                        }
                    } else {
                        error "No build number or workspace directory found in environment variables"
                    }
                }
            }
        }

        // stage('Build and Tests') {
        //     parallel {
        //         stage('Virtual drive tests on Linux') {
        //             agent {
        //                 docker {
        //                     label "worker"
        //                     image LIN_DOCKER_IMAGE
        //                 }
        //             }
        //             stages {
        //                 stage('Run no-connection tests') {
        //                     steps {
        //                         sh "python${DEFAULT_PYTHON_VERSION} -m tox -e ${RUN_PYTHON_VERSIONS} -- " +
        //                             "-m virtual " +
        //                             "--setup tests.setups.virtual_drive.TESTS_SETUP"
        //                     }
        //                     post {
        //                         always {
        //                             junit "pytest_reports/*.xml"
        //                         }
        //                     }
        //                 }
        //             }
        //         }

        //         stage('Build and publish') {
        //             stages {
        //                 stage('Build') {
        //                     agent {
        //                         docker {
        //                             label SW_NODE
        //                             image WIN_DOCKER_IMAGE
        //                         }
        //                     }
        //                     stages {
        //                         stage('Build wheels') {
        //                             steps {
        //                                 bat "py -${DEFAULT_PYTHON_VERSION} -m tox -e build"
        //                                 stash includes: 'dist\\*', name: 'build'
        //                                 archiveArtifacts artifacts: "dist\\*"
        //                             }
        //                         }
        //                         stage('Make a static type analysis') {
        //                             steps {
        //                                 bat "py -${DEFAULT_PYTHON_VERSION} -m tox -e type"
        //                             }
        //                         }
        //                         stage('Check formatting') {
        //                             steps {
        //                                 bat "py -${DEFAULT_PYTHON_VERSION} -m tox -e format"
        //                             }
        //                         }
        //                         stage('Generate documentation') {
        //                             steps {
        //                                 bat "py -${DEFAULT_PYTHON_VERSION} -m tox -e docs"
        //                                 bat """
        //                                     "C:\\Program Files\\7-Zip\\7z.exe" a -r docs.zip -w _docs -mem=AES256
        //                                 """
        //                                 stash includes: 'docs.zip', name: 'docs'
        //                             }
        //                         }
        //                         stage("Run unit tests") {
        //                             steps {
        //                                 bat "py -${DEFAULT_PYTHON_VERSION} -m tox -e ${RUN_PYTHON_VERSIONS} -- " +
        //                                         "-m \"not ethernet and not soem and not canopen and not virtual and not soem_multislave\" " +
        //                                         "--cov=ingeniamotion"
        //                             }
        //                             post {
        //                                 always {
        //                                     bat "move .coverage .coverage_unit_tests"
        //                                     junit "pytest_reports\\*.xml"
        //                                     // Delete the junit after publishing it so it not re-published on the next stage
        //                                     bat "del /S /Q pytest_reports\\*.xml"
        //                                     stash includes: '.coverage_unit_tests', name: '.coverage_unit_tests'
        //                                     script {
        //                                         coverage_stashes.add(".coverage_unit_tests")
        //                                     }
        //                                 }
        //                             }
        //                         }
        //                         stage("Run virtual drive tests") {
        //                             steps {
        //                                 bat "py -${DEFAULT_PYTHON_VERSION} -m tox -e ${RUN_PYTHON_VERSIONS} -- " +
        //                                         "-m virtual " +
        //                                         "--setup tests.setups.virtual_drive.TESTS_SETUP "  +
        //                                         "--cov=ingeniamotion"
        //                             }
        //                             post {
        //                                 always {
        //                                     bat "move .coverage .coverage_virtual"
        //                                     junit "pytest_reports\\*.xml"
        //                                     // Delete the junit after publishing it so it not re-published on the next stage
        //                                     bat "del /S /Q pytest_reports\\*.xml"
        //                                     stash includes: '.coverage_virtual', name: '.coverage_virtual'
        //                                     script {
        //                                         coverage_stashes.add(".coverage_virtual")
        //                                     }
        //                                 }
        //                             }
        //                         }
        //                     }
        //                 }
        //                 stage('Publish documentation') {
        //                     when {
        //                         beforeAgent true
        //                         branch BRANCH_NAME_MASTER
        //                     }
        //                     agent {
        //                         label "worker"
        //                     }
        //                     steps {
        //                         unstash 'docs'
        //                         unzip zipFile: 'docs.zip', dir: '.'
        //                         publishDistExt("_docs", DISTEXT_PROJECT_DIR, false)
        //                     }
        //                 }
        //                 stage('Publish to pypi') {
        //                     when {
        //                         beforeAgent true
        //                         branch BRANCH_NAME_MASTER
        //                     }
        //                     agent {
        //                         docker {
        //                             label 'worker'
        //                             image "ingeniacontainers.azurecr.io/publisher:1.8"
        //                         }
        //                     }
        //                     steps {
        //                         unstash 'build'
        //                         publishPyPi("dist/*")
        //                     }
        //                 }
        //             }
        //         }

        //         stage('HW Tests CanOpen and Ethernet') {
        //             options {
        //                 lock(CAN_NODE_LOCK)
        //             }
        //             agent {
        //                 label CAN_NODE
        //             }
        //             stages {
        //                 stage("CanOpen Everest") {
        //                     steps {
        //                         runTestHW("canopen", "CAN_EVE_SETUP")
        //                     }
        //                 }
        //                 stage("Ethernet Everest") {
        //                     steps {
        //                         runTestHW("ethernet", "ETH_EVE_SETUP")
        //                     }
        //                 }
        //                 stage("CanOpen Capitan") {
        //                     steps {
        //                         runTestHW("canopen", "CAN_CAP_SETUP")
        //                     }
        //                 }
        //                 stage("Ethernet Capitan") {
        //                     when {
        //                         // Remove this after fixing INGK-982
        //                         expression { false }
        //                     }
        //                     steps {
        //                         runTestHW("ethernet", "ETH_CAP_SETUP")
        //                     }
        //                 }
        //             }
        //         }
        //         stage('Hw Tests Ethercat') {
        //             options {
        //                 lock(ECAT_NODE_LOCK)
        //             }
        //             agent {
        //                 label ECAT_NODE
        //             }
        //             stages {
        //                 stage("Ethercat Everest") {
        //                     when {
        //                         // Remove this after fixing INGK-983
        //                         expression { false }
        //                     }
        //                     steps {
        //                         runTestHW("soem", "ECAT_EVE_SETUP")
        //                     }
        //                 }
        //                 stage("Ethercat Capitan") {
        //                     steps {
        //                         runTestHW("soem", "ECAT_CAP_SETUP")
        //                     }
        //                 }
        //                 stage("Ethercat Multislave") {
        //                     steps {
        //                         runTestHW("soem_multislave", "ECAT_MULTISLAVE_SETUP")
        //                     }
        //                 }
        //             }
        //         }
        //     }
        // }

        // stage('Publish coverage') {
        //     agent {
        //         docker {
        //             label SW_NODE
        //             image WIN_DOCKER_IMAGE
        //         }
        //     }
        //     steps {
        //         script {
        //             def coverage_files = ""

        //             for (coverage_stash in coverage_stashes) {
        //                 unstash coverage_stash
        //                 coverage_files += " " + coverage_stash
        //             }
        //             bat "py -${DEFAULT_PYTHON_VERSION} -m tox -e coverage -- ${coverage_files}"
        //         }
        //         recordCoverage(tools: [[parser: 'COBERTURA', pattern: 'coverage.xml']])
        //         archiveArtifacts artifacts: '*.xml'
        //     }
        // }
    }
}
