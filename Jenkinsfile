
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
    if (env.BRANCH_NAME == BRANCH_NAME_MASTER || env.BRANCH_NAME.contains(BRANCH_NAME_RELEASE))
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
                    del /f "Pipfile.lock"
                """
            }

        stage('Install deps') {
            bat '''
                pipenv install --dev
            '''
        }

        stage('Docs') {
            bat '''
                pipenv run sphinx-build -b html docs _docs
            '''
        }

        stage('Build libraries')
        {
            bat '''
                pipenv run python setup.py bdist_wheel
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
