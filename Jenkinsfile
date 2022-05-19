
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

        stage('Remove all previous files')
            {
                bat """
                    rmdir /Q /S "_build"
                    rmdir /Q /S "_deps"
                    rmdir /Q /S "_install"
                    rmdir /Q /S "_dist"
                    rmdir /Q /S "build"
                    rmdir /Q /S "_docs"
                """
            }

        stage('Install deps') {
            bat '''
                python -m venv venv
                venv\\Scripts\\python.exe -m pip install -r requirements\\dev-requirements.txt
            '''
        }

        stage('Docs') {
            bat '''
                venv\\Scripts\\python.exe -m sphinx-build -b html docs _docs
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
