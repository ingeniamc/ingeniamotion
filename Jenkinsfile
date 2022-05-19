
/*
 * ingeniamotion
 *
 * Copyright (c) 2020 Ingenia Motion Control.
 */


def NODE_NAME = "sw"
def BRANCH_NAME_RELEASE = "release"
def BRANCH_NAME_MASTER = "master"

node(NODE_NAME) {
    deleteDir()
    if (true)
    {
        stage('Checkout') {
            checkout scm
        }

        stage('Install deps') {
            bat '''
                python -m venv venv
                venv\\Scripts\\activate.bat
                pip install -r requirements\\dev-requirements.txt
            '''
        }

        stage('Docs') {
            bat '''
                sphinx-build -b html docs _docs
            '''
        }

        stage('Build libraries')
        {
            bat '''
                python setup.py bdist_wheel
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
