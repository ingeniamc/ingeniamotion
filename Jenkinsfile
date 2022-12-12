def SW_NODE = "windows-slave"
def ECAT_NODE = "ecat-test"
def ECAT_NODE_LOCK = "test_execution_lock_ecat"
def CAN_NODE = "canopen-test"
def CAN_NODE_LOCK = "test_execution_lock_can"


pipeline {
    agent none
    stages {
        stage('Build wheels and documentation') {
            agent {
                docker {
                    label SW_NODE
                    image 'ingeniacontainers.azurecr.io/ingeniamotion-builder'
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
                            venv\\Scripts\\python.exe -m pip install -r requirements\\dev-requirements.txt
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
                stage('Generate documentation') {
                    steps {
                        bat '''
                            cd C:\\Users\\ContainerAdministrator\\ingeniamotion
                            venv\\Scripts\\python.exe -m sphinx -b html docs _docs
                        '''
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
                stage('Run EtherCAT tests') {
                    steps {
                        bat '''
                            venv\\Scripts\\python.exe -m pytest tests --protocol soem --slave 0 --html=pytest_ecat_slave_0_report.html --self-contained-html
                            venv\\Scripts\\python.exe -m pytest tests --protocol soem --slave 1 --html=pytest_ecat_slave_1_report.html --self-contained-html
                            exit /b 0
                        '''
                    }
                }
                stage('Save test results') {
                    steps {
                        archiveArtifacts artifacts: '*.html'
                    }
                }
            }
        }
        stage('CANopen and Ethernet tests') {
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
                stage('Run CANopen tests') {
                    steps {
                        bat '''
                            venv\\Scripts\\python.exe -m pytest tests --protocol canopen --slave 0 --html=pytest_can_slave_0_report.html --self-contained-html
                            venv\\Scripts\\python.exe -m pytest tests --protocol canopen --slave 1 --html=pytest_can_slave_1_report.html --self-contained-html
                            exit /b 0
                        '''
                    }
                }
                stage('Run Ethernet tests') {
                    steps {
                        bat '''
                            venv\\Scripts\\python.exe -m pytest tests --protocol eoe --slave 0 --html=pytest_eth_slave_0_report.html --self-contained-html
                            venv\\Scripts\\python.exe -m pytest tests --protocol eoe --slave 1 --html=pytest_eth_slave_1_report.html --self-contained-html
                            exit /b 0
                        '''
                    }
                }
                stage('Save test results') {
                    steps {
                        archiveArtifacts artifacts: '*.html'
                    }
                }
            }
        }
    }
}