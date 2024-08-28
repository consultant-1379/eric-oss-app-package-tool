#!/usr/bin/env groovy
def bob2 = "bob/bob -r \${WORKSPACE}/ruleset2.0.yaml"

pipeline {
    agent {
        node {
            label NODE_LABEL
        }
    }

    environment {
        CREDENTIALS_SELI_ARTIFACTORY = credentials('SELI_ARTIFACTORY')
        MAVEN_CLI_OPTS = "-Duser.home=${env.HOME} -s ${env.WORKSPACE}/settings.xml"
        BRANCH = "dirty"
        BUILD_NUMBER = "${env.BUILD_NUMBER}"
    }

    stages {

        stage('Clean') {
            steps {
                sh 'git clean -xdff'
                sh 'git submodule sync'
                sh 'git submodule update --init --recursive'
                echo 'Inject settings.xml into workspace:'
                configFileProvider([configFile(fileId: "${env.SETTINGS_CONFIG_FILE_NAME}", targetLocation: "${env.WORKSPACE}")]) {}
                archiveArtifacts allowEmptyArchive: true, artifacts: 'ruleset2.0.yaml, precodereview.Jenkinsfile'
                sh "${bob2} clean"
            }
        }

        stage('Run Unit Test') {
            steps {
                sh "${bob2} test"
            }
        }


        stage('Update Bob Files') {
            //Write project name to file for Bob'
            //Write project version to file for Bob
            steps {
                sh "${bob2} bob_project_name"
                sh "${bob2} bob_gerrit_version"
            }
        }

        stage('Create and push snapshot artifacts') {
            steps {
                sh "${bob2} init-gerrit image"
            }
        }

        stage('Run acceptance tests ') {
            environment{
                DOCKER_IMG = sh(script: "cat .bob/var.image-name | tr -d '\n' ",trim: true, returnStdout: true)
                WORKSPACE = sh(script: "echo ${env.WORKSPACE} | tr -d '\n' ", returnStdout: true)
            }
            steps {
                sh "${bob2} create_csars"
                sh '''
                        if [ -f acceptance.csar ] && [ -f acceptance-helm3.csar ] && [ -f acceptance-multi.csar ] && [ -f lightweight.csar ]; then
                            echo "CSAR files created successfully"
                        else
                            echo "One or more CSAR files not created"
                            echo "Generated CSARs are:"
                            ls -l *.csar
                            currentBuild.result="FAILURE"
                        fi
                    '''

                sh 'echo "Run robot tests on generated CSAR"';
                sh "${bob2} robot"
            }
        }
    }
    post {
        always {
            sh "${bob2} docker_remove_local_images"
            echo "Finished"
        }
    }
}
