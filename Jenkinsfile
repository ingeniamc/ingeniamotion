
/*
 * ingeniamotion
 *
 * Copyright (c) 2020 Ingenia Motion Control.
 */

properties([
  buildDiscarder(logRotator(artifactNumToKeepStr: '10', daysToKeepStr: '30')),
])

node('windows') {
    deleteDir()

    stage('Windows checkout') {
        checkout([$class: 'GitSCM',
                branches: [ [name: '*/master'],
                            [name: '*/develop'],
                            [name: '*/feature/INGM-27-add-jenkins-ci-process']
                        ],
                doGenerateSubmoduleConfigurations: false,
                extensions: [],
                submoduleCfg: [],
                userRemoteConfigs: [[credentialsId: 'jenkins-bitbucket',
                    url: 'https://bitbucket.org/ingeniamc/libs-ingeniamotion.git']]])
    }


    stage('Install deps') {
        bat '''
            python -m pipenv install --dev
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
        archiveArtifacts artifacts: 'dist/*'
    }

    stage('Deploy') {

    }
}
