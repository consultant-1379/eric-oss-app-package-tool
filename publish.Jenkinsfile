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

    options {
        timestamps()
    }

    stages {

        stage('Setup git') {
            steps {
                sh("git config --global user.email 'you@example.com'")
                sh("git config --global user.name 'Jenkins User'")
                sh "git remote set-url --push origin ssh://gerrit.ericsson.se:29418/OSS/com.ericsson.oss.ae/eric-oss-app-package-tool"
            }
        }


        stage('Clean') {
            steps {
                sh 'git clean -xdff'
                sh 'git submodule sync'
                sh 'git submodule update --init --recursive'
                echo 'Inject settings.xml into workspace:'
                configFileProvider([configFile(fileId: "${env.SETTINGS_CONFIG_FILE_NAME}", targetLocation: "${env.WORKSPACE}")]) {}
                archiveArtifacts allowEmptyArchive: true, artifacts: 'ruleset2.0.yaml, precodereview.Jenkinsfile'
                sh "${bob2} clean:rm"
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
                sh "${bob2} bob_release_version"
            }
        }

        stage('Update version on pom files') {
            steps {
                sh "${bob2} update_pom_version"
            }
        }

        stage('Create Release Branch') {
            steps {
                sh "${bob2} update_pom_version git_create_branch"
            }
        }

        stage('clean install project') {
            steps {
                sh "${bob2} clean:mvn-clean"
            }
        }

        stage('Create and push snapshot artifacts') {
            steps {
                sh "${bob2} init-release image"
            }
        }

        stage('Run acceptance tests ') {
            environment {
                DOCKER_IMG = sh(script: "cat .bob/var.image-name | tr -d '\n' ", trim: true, returnStdout: true)
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
        stage('Creating ADP Properties') {
            steps {
                sh 'echo "IMAGE_REPO=armdocker.rnd.ericsson.se/proj-eric-oss-dev-test/$(<.project_name)/releases/$(<.project_name):$(<.project_version)" > artifact.properties'
                archiveArtifacts artifacts: 'artifact.properties', fingerprint: true
            }
        }

        stage('Commit release version changes') {
            steps {
                    sh('''
                        project_version=$(cat .project_version);
                        git add -A;
                        git commit -m "Committing version ${project_version}";
                        git tag -d ${project_version} || echo 'no tag  found to delete';
                        git tag ${project_version};
                        echo -n $project_version > .tag_version;
                        git log -3;
                    ''')
            }
        }
        stage('Merge release to branch') {
            steps {
                    sh('''
                        git branch -D master || echo 'no local branch found';
                        git checkout -b master;
                    ''')
                }
        }
        stage('Delete Release Branch') {
            steps {
                sh "${bob2} git_delete_branch"
            }
        }

        stage('Update versions and add -SNAPSHOT') {
            steps {
                sh "${bob2} update_version_snapshot"
            }
        }


        stage('Commit snapshot version changes') {
            steps {
                    sh('''
                        project_version=$(cat .project_version);
                        git add -A;
                        git reset -- .tag_version;
                        git commit -m "Committing SNAPSHOT version ${project_version}";
                        git log -3;
                    ''')
            }
        }

        stage('Merge snapshot to branch and push all changes') {
            steps {
                    sh('''
                        git push origin master;
                        git push origin master $(cat .tag_version);
                        rm .tag_version;
                    ''')
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
