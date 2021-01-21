
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
                branches: [[name: '*/master'], [name: '*/develop']], 
                doGenerateSubmoduleConfigurations: false, 
                extensions: [], 
                submoduleCfg: [],
                userRemoteConfigs: [[credentialsId: 'jenkins-bitbucket', 
                    url: 'https://bitbucket.org/ingeniamc/libs-ingeniamotion-2.git']]])
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
    stage('Archive') {
        bat '''
            pipenv run python setup.py bdist_wheel
        '''
        archiveArtifacts artifacts: 'dist/*'
    }

    stage('Deploy') {
        
    }
}
