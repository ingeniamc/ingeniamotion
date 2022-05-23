
/*
 * ingeniamotion
 *
 * Copyright (c) 2020 Ingenia Motion Control.
 */


def SW_NODE = "sw"
def ECAT_NODE = "ecat-test-slave"
def CAN_NODE = "canopen-test-slave"
def BRANCH_NAME_RELEASE = "release"
def BRANCH_NAME_DEVELOP = "develop"

if (env.BRANCH_NAME == BRANCH_NAME_DEVELOP ||
env.BRANCH_NAME.contains(BRANCH_NAME_RELEASE) ||
(env.CHANGE_ID && env.BRANCH_NAME.startsWith("PR-") &&
                (env.CHANGE_TARGET == BRANCH_NAME_DEVELOP || env.CHANGE_TARGET.contains(BRANCH_NAME_RELEASE)))){
    lock('test_execution_lock_ecat') {
        node(ECAT_NODE) {
            deleteDir()
            stage('Checkout') {
                checkout scm
            }

            stage('Install deps') {
                bat '''
                    python -m venv venv
                    venv\\Scripts\\python.exe -m pip install -r requirements\\dev-requirements.txt
                '''
            }

            stage('Run EtherCAT embedded tests') {
                bat '''
                    venv\\Scripts\\python.exe -m pytest tests --protocol soem
                '''
            }
        }
    }

    lock('test_execution_lock_can') {
        node(CAN_NODE) {
            deleteDir()
            stage('Checkout') {
                checkout scm
            }

            stage('Install deps') {
                bat '''
                    python -m venv venv
                    venv\\Scripts\\python.exe -m pip install -r requirements\\dev-requirements.txt
                '''
            }

            stage('Run CANopen tests') {
                bat '''
                    venv\\Scripts\\python.exe -m pytest tests --protocol canopen
                '''
            }

            stage('Run Ethernet tests') {
                bat '''
                    venv\\Scripts\\python.exe -m pytest tests --protocol eoe
                '''
            }
        }
    }
    if (env.BRANCH_NAME != BRANCH_NAME_DEVELOP || env.CHANGE_TARGET != BRANCH_NAME_DEVELOP) {
        node(SW_NODE) {
            deleteDir()
            stage('Checkout') {
                checkout scm
            }

            stage('Install deps') {
                bat '''
                    python -m venv venv
                    venv\\Scripts\\python.exe -m pip install -r requirements\\dev-requirements.txt
                '''
            }

            stage('Docs') {
                bat '''
                     venv\\Scripts\\python.exe -m sphinx -b html docs _docs
                '''
            }

            stage('Build libraries')
            {
                bat '''
                     venv\\Scripts\\python.exe setup.py bdist_wheel
                '''
            }

            stage('Archive') {
                bat '''

                    "C:/Program Files/7-Zip/7z.exe" a -r docs.zip -w _docs -mem=AES256
                '''
                archiveArtifacts artifacts: 'dist/*, docs.zip'
            }
        }
    }
}




