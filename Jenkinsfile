def SW_NODE = "windows-slave"
def ECAT_NODE = "ecat-test"
def ECAT_NODE_LOCK = "test_execution_lock_ecat"
def CAN_NODE = "canopen-test"
def CAN_NODE_LOCK = "test_execution_lock_can"


pipeline {
    agent none
    parameters {
        choice(
            choices: ['Smoke', 'All'], 
            name: 'TESTS'
        )
    }
    stages {
        stage('Build wheels and documentation') {
            agent {
                docker {
                    label SW_NODE
                    image 'ingeniacontainers.azurecr.io/win-python-builder:1.0'
                }
            }
            stages {
                stage('Clone repository') {
                    steps {
                        bat """
                            cd C:\\Users\\ContainerAdministrator
                            git clone https://github.com/ingeniamc/ingeniamotion.git
                            cd ingeniamotion
                            git checkout ${env.GIT_COMMIT}
                        """
                    }
                 }
                stage('Install deps') {
                    steps {
                        bat '''
                            cd C:\\Users\\ContainerAdministrator\\ingeniamotion
                            python -m venv venv
                            venv\\Scripts\\python.exe -m pip install -r requirements\\dev-requirements.txt -r requirements\\test-requirements.txt
                            venv\\Scripts\\python.exe -m pip install -e .
                        '''
                    }
                }
                stage('Build wheels') {
                    steps {
                        bat '''
                             cd C:\\Users\\ContainerAdministrator\\ingeniamotion
                             venv\\Scripts\\python.exe setup.py bdist_wheel
                        '''
                    }
                }
                stage('Make a static type analysis') {
                    steps {
                        bat """
                            cd C:\\Users\\ContainerAdministrator\\ingeniamotion
                            venv\\Scripts\\python.exe -m mypy ingeniamotion
                        """
                    }
                }
                stage('Check formatting') {
                    steps {
                        bat """
                            cd C:\\Users\\ContainerAdministrator\\ingeniamotion
                            venv\\Scripts\\python.exe -m black -l 100 --check ingeniamotion tests
                        """
                    }
                }
                stage('Generate documentation') {
                    steps {
                        bat '''
                            cd C:\\Users\\ContainerAdministrator\\ingeniamotion
                            venv\\Scripts\\python.exe -m sphinx -b html docs _docs
                        '''
                    }
                }
                stage("Run virtual drive tests") {
                    steps {
                        bat """
                            cd C:\\Users\\ContainerAdministrator\\ingeniamotion
                            venv\\Scripts\\python.exe -m pytest tests -m virtual --protocol virtual --junitxml=pytest_reports\\pytest_virtual_report.xml
                            move .coverage ${env.WORKSPACE}\\.coverage_virtual
                            XCOPY pytest_reports ${env.WORKSPACE}\\pytest_reports /i
                            exit /b 0
                        """
                    }
                }
                stage('Save test results') {
                    steps {
                        stash includes: '.coverage_virtual', name: 'coverage_reports'
                        stash includes: 'pytest_reports/', name: 'test_reports'
                    }
                }
                stage('Archive') {
                    steps {
                        bat """
                            cd C:\\Users\\ContainerAdministrator\\ingeniamotion
                            "C:\\Program Files\\7-Zip\\7z.exe" a -r docs.zip -w _docs -mem=AES256
                            XCOPY dist ${env.WORKSPACE}\\dist /i
                            XCOPY docs.zip ${env.WORKSPACE}
                        """
                        archiveArtifacts artifacts: "dist\\*, docs.zip"
                    }
                }
            }
        }
        stage('EtherCAT tests') {
            // Remove once EtherCAT tests are operational.
            when {
                expression { false }
            }
            options {
                lock(ECAT_NODE_LOCK)
            }
            agent {
                label ECAT_NODE
            }
            stages {
                stage('Checkout') {
                    steps {
                        checkout scm
                    }
                }
                stage('Install deps') {
                    steps {
                        bat '''
                            python -m venv venv
                            venv\\Scripts\\python.exe -m pip install -r requirements\\test-requirements.txt
                        '''
                    }
                }
                stage('Update drives FW') {
                    steps {
                        bat '''
                            venv\\Scripts\\python.exe tests\\load_FWs.py soem
                        '''
                    }
                }
                stage('Run EtherCAT all tests') {
                    when {
                        anyOf{
                            branch 'master';
                            branch 'develop';
                            expression { params.TESTS == 'All' }
                        }
                    }
                    steps {
                        bat '''
                            venv\\Scripts\\python.exe -m pytest tests --protocol soem --slave 0 --junitxml=pytest_reports/pytest_ethercat_0_report.xml
                            venv\\Scripts\\python.exe -m pytest tests --protocol soem --slave 1 --junitxml=pytest_reports/pytest_ethercat_1_report.xml
                            move .coverage .coverage_ethercat
                            exit /b 0
                        '''
                    }
                }
                stage('Run EtherCAT smoke tests') {
                    when {
                        allOf{
                            not{ branch 'master' };
                            not{ branch 'develop' };
                            expression { params.TESTS == 'Smoke' }
                        }
                    }
                    steps {
                        bat '''
                            venv\\Scripts\\python.exe -m pytest tests -m smoke --protocol soem --slave 0 --junitxml=pytest_reports/pytest_ethercat_0_report.xml
                            venv\\Scripts\\python.exe -m pytest tests -m smoke --protocol soem --slave 1 --junitxml=pytest_reports/pytest_ethercat_1_report.xml
                            move .coverage .coverage_ethercat
                            exit /b 0
                        '''
                    }
                }
                stage('Save test results') {
                    steps {
                        stash includes: '.coverage_ethercat', name: 'coverage_reports'
                        stash includes: 'pytest_reports/', name: 'test_reports'
                    }
                }
            }
        }
        stage('CANopen and Ethernet tests') {
            options {
                lock(CAN_NODE_LOCK)
            }
            agent {
                label CAN_NODE
            }
            stages {
                stage('Checkout') {
                    steps {
                        checkout scm
                    }
                }
                stage('Install deps') {
                    steps {
                        bat '''
                            python -m venv venv
                            venv\\Scripts\\python.exe -m pip install -r requirements\\test-requirements.txt
                        '''
                    }
                }
                stage('Update drives FW') {
                    steps {
                        bat '''
                            venv\\Scripts\\python.exe tests\\load_FWs.py canopen
                        '''
                    }
                }
                stage('Run CANopen smoke tests') {
                    when {
                        allOf{
                            not{ branch 'master' };
                            not{ branch 'develop' };
                            expression { params.TESTS == 'Smoke' }
                        }
                    }
                    steps {
                        //unstash 'test_reports' Uncomment once EtherCAT tests are operational.
                        bat '''
                            venv\\Scripts\\python.exe -m pytest tests -m smoke --protocol canopen --slave 0 --junitxml=pytest_reports/pytest_canopen_0_report.xml
                            venv\\Scripts\\python.exe -m pytest tests -m smoke --protocol canopen --slave 1 --junitxml=pytest_reports/pytest_canopen_1_report.xml
                            move .coverage .coverage_canopen
                            exit /b 0
                        '''
                    }
                }
                stage('Run CANopen all tests') {
                    when {
                        anyOf{
                            branch 'master';
                            branch 'develop';
                            expression { params.TESTS == 'All' }
                        }
                    }
                    steps {
                        //unstash 'test_reports' Uncomment once EtherCAT tests are operational.
                        bat '''
                            venv\\Scripts\\python.exe -m pytest tests --protocol canopen --slave 0 --junitxml=pytest_reports/pytest_canopen_0_report.xml
                            venv\\Scripts\\python.exe -m pytest tests --protocol canopen --slave 1 --junitxml=pytest_reports/pytest_canopen_1_report.xml
                            move .coverage .coverage_canopen
                            exit /b 0
                        '''
                    }
                }
                stage('Run Ethernet smoke tests') {
                    // Add tests of slave 1 after fixing CAP-924
                    when {
                        allOf{
                            not{ branch 'master' };
                            not{ branch 'develop' };
                            expression { params.TESTS == 'Smoke' }
                        }
                    }
                    steps {
                        bat '''
                            venv\\Scripts\\python.exe -m pytest tests -m smoke --protocol eoe --slave 0 --junitxml=pytest_reports/pytest_ethernet_0_report.xml
                            move .coverage .coverage_ethernet
                            exit /b 0
                        '''
                    }
                }
                stage('Run Ethernet all tests') {
                    // Add tests of slave 1 after fixing CAP-924
                    when {
                        anyOf{
                            branch 'master';
                            branch 'develop';
                            expression { params.TESTS == 'All' }
                        }
                    }
                    steps {
                        bat '''
                            venv\\Scripts\\python.exe -m pytest tests --protocol eoe --slave 0 --junitxml=pytest_reports/pytest_ethernet_0_report.xml
                            move .coverage .coverage_ethernet
                            exit /b 0
                        '''
                    }
                }
                stage('Save test results') {
                    steps {
                        //unstash 'coverage_reports' Uncomment once EtherCAT tests are operational.
                        // Add .coverage_ethercat to the combine command once EtherCAT tests are operational.
                        unstash 'coverage_reports'
                        unstash 'test_reports'
                        bat '''
                            venv\\Scripts\\python.exe -m coverage combine .coverage_ethernet .coverage_canopen .coverage_virtual
                            venv\\Scripts\\python.exe -m coverage xml --include=ingeniamotion/*
                        '''
                        publishCoverage adapters: [coberturaReportAdapter('coverage.xml')]
                        archiveArtifacts artifacts: '*.xml, pytest_reports\\*'
                        bat '''
                            venv\\Scripts\\python.exe -m tests.combine_reports -i pytest_reports/ -o combined_report.xml
                        '''
                        junit 'combined_report.xml'
                    }
                }
            }
        }
    }
}