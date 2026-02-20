def runPythonTask(String taskScript) {
    writeFile(
        file: '.jenkins_python_task.sh',
        text: """#!/usr/bin/env bash
set -euo pipefail
${taskScript}
"""
    )
    sh(
        script: '''#!/usr/bin/env bash
set -euo pipefail
chmod +x .jenkins_python_task.sh
docker run --rm \
  -u "$(id -u):$(id -g)" \
  -v "$PWD:/workspace" \
  -w /workspace \
  "${PYTHON_IMAGE}" \
  bash /workspace/.jenkins_python_task.sh
'''
    )
}

pipeline {
    agent any

    options {
        disableConcurrentBuilds()
        buildDiscarder(logRotator(numToKeepStr: '20'))
        timeout(time: 45, unit: 'MINUTES')
        skipDefaultCheckout(true)
        durabilityHint('MAX_SURVIVABILITY')
    }

    stages {
        stage('Checkout') {
            steps {
                checkout scm
                script {
                    if (!fileExists('Jenkinsfile')) {
                        error('Jenkinsfile missing at repo root.')
                    }
                    def allowed = ['main', 'develop']
                    if (env.BRANCH_NAME && !(env.BRANCH_NAME in allowed)) {
                        error("Branch policy violation: ${env.BRANCH_NAME} not in ${allowed}")
                    }
                }
            }
        }

        stage('Initialize') {
            steps {
                script {
                    // Load values from Jenkins global env/job env, with safe defaults.
                    env.APP_NAME = env.APP_NAME?.trim() ?: 'secure-flask-app'
                    env.APP_PORT = env.APP_PORT?.trim() ?: '3000'
                    env.COVERAGE_MIN = env.COVERAGE_MIN?.trim() ?: '80'
                    env.PYTHON_IMAGE = env.PYTHON_IMAGE?.trim() ?: 'python:3.12-slim'
                    env.TRIVY_CACHE_DIR = env.TRIVY_CACHE_DIR?.trim() ?: '/var/lib/jenkins/.cache/trivy'
                    env.TRIVY_TIMEOUT = env.TRIVY_TIMEOUT?.trim() ?: '5m'
                    env.USE_ECR = env.USE_ECR?.trim() ?: 'true'
                    env.ECR_PUSH_LATEST = env.ECR_PUSH_LATEST?.trim() ?: 'false'
                    env.AWS_REGION = env.AWS_REGION?.trim() ?: 'eu-west-1'
                    env.DEPLOY_CONTAINER = env.DEPLOY_CONTAINER?.trim() ?: 'secure-flask-app'
                    env.EC2_USER = env.EC2_USER?.trim() ?: 'ec2-user'
                    env.EC2_SSH_CREDENTIALS_ID = env.EC2_SSH_CREDENTIALS_ID?.trim() ?: 'ec2_ssh'

                    def missing = []
                    if (!env.REGISTRY?.trim()) {
                        missing << 'REGISTRY'
                    }
                    if (!env.EC2_HOST?.trim()) {
                        missing << 'EC2_HOST'
                    }
                    if (!missing.isEmpty()) {
                        error("Missing required Jenkins environment variables: ${missing.join(', ')}")
                    }

                    env.IMAGE_NAME = "${env.REGISTRY}/${env.APP_NAME}"

                    if (env.USE_ECR.toBoolean()) {
                        def awsCliPresent = sh(returnStatus: true, script: 'command -v aws >/dev/null 2>&1') == 0
                        if (!awsCliPresent) {
                            error('aws CLI is required for ECR')
                        }
                    }
                }
            }
        }

        stage('Install / Build') {
            steps {
                script {
                    runPythonTask('''
                        python -m venv .venv
                        . .venv/bin/activate
                        pip install --upgrade pip
                        pip install -r app/requirements.txt -r app/requirements-dev.txt
                        pip check
                    '''.stripIndent().trim())
                }
            }
        }

        stage('Test') {
            steps {
                script {
                    runPythonTask("""
                        . .venv/bin/activate
                        export PYTHONPATH=/workspace
                        pytest -q --cov=app --cov-report=xml --cov-fail-under=${env.COVERAGE_MIN}
                    """.stripIndent().trim())
                }
            }
        }

        stage('Security Gates') {
            steps {
                script {
                    runPythonTask('''
                        . .venv/bin/activate
                        bandit -q -r app
                        pip-audit -r app/requirements.txt
                    '''.stripIndent().trim())
                    // Trivy checks intentionally disabled for now.
                }
            }
        }

        stage('Docker Build') {
            steps {
                script {
                    def gitCommit = sh(returnStdout: true, script: 'git rev-parse --short HEAD').trim()
                    def buildTs = sh(returnStdout: true, script: "date -u +%Y-%m-%dT%H:%M:%SZ").trim()
                    sh """
                        set -euo pipefail
                        docker build -t ${APP_NAME}:${BUILD_NUMBER} \
                          --build-arg BUILD_NUMBER=${BUILD_NUMBER} \
                          --build-arg GIT_COMMIT=${gitCommit} \
                          --build-arg BUILD_TIMESTAMP=${buildTs} \
                          -f app/Dockerfile app
                        docker tag ${APP_NAME}:${BUILD_NUMBER} ${IMAGE_NAME}:${BUILD_NUMBER}
                        docker tag ${APP_NAME}:${BUILD_NUMBER} ${IMAGE_NAME}:latest
                    """
                }
            }
        }

        stage('Image Scan') {
            steps {
                sh '''
                    set -euo pipefail
                    # Trivy image scan temporarily disabled.
                    echo "Skipping Trivy image scan."
                '''
            }
        }

        stage('Push Image') {
            steps {
                script {
                    if (env.USE_ECR.toBoolean()) {
                        sh '''
                            set -euo pipefail
                            aws ecr get-login-password --region "${AWS_REGION}" | docker login --username AWS --password-stdin "${REGISTRY}"
                            docker push ${IMAGE_NAME}:${BUILD_NUMBER}
                        '''
                        if (env.ECR_PUSH_LATEST.toBoolean()) {
                            sh 'docker push ${IMAGE_NAME}:latest'
                        } else {
                            echo 'Skipping latest tag push for immutable ECR repository.'
                        }
                        sh 'docker logout "${REGISTRY}"'
                    } else {
                        withCredentials([usernamePassword(credentialsId: 'registry_creds', usernameVariable: 'REGISTRY_USER', passwordVariable: 'REGISTRY_PASS')]) {
                            sh '''
                                set -euo pipefail
                                echo "${REGISTRY_PASS}" | docker login -u "${REGISTRY_USER}" --password-stdin "${REGISTRY}"
                                docker push ${IMAGE_NAME}:${BUILD_NUMBER}
                            '''
                            if (env.ECR_PUSH_LATEST.toBoolean()) {
                                sh 'docker push ${IMAGE_NAME}:latest'
                            }
                            sh 'docker logout "${REGISTRY}"'
                        }
                    }
                }
            }
        }

        stage('Deploy to EC2') {
            steps {
                sshagent(credentials: [env.EC2_SSH_CREDENTIALS_ID]) {
                    sh '''
                        set -euo pipefail
                        ssh -o StrictHostKeyChecking=no ${EC2_USER}@${EC2_HOST} \
                          "IMAGE_NAME='${IMAGE_NAME}:${BUILD_NUMBER}' REGISTRY='${REGISTRY}' APP_NAME='${APP_NAME}' DEPLOY_CONTAINER='${DEPLOY_CONTAINER}' USE_ECR='${USE_ECR}' AWS_REGION='${AWS_REGION}' bash -s" \
                          < scripts/deploy_remote.sh
                    '''
                }
            }
        }

        stage('Post-Deployment Verification') {
            steps {
                sh '''
                    set -euo pipefail
                    curl -fsS "http://${EC2_HOST}/health"
                '''
            }
        }

        stage('Cleanup') {
            steps {
                sh '''
                    set -euo pipefail
                    docker container prune -f
                    docker image prune -f
                '''
            }
        }
    }

    post {
        failure {
            echo 'Pipeline failed. Review logs for details.'
        }
        always {
            cleanWs()
        }
    }
}
