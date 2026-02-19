pipeline {
    agent any

    options {
        disableConcurrentBuilds()
        buildDiscarder(logRotator(numToKeepStr: '20'))
        timeout(time: 45, unit: 'MINUTES')
        skipDefaultCheckout(true)
        durabilityHint('MAX_SURVIVABILITY')
    }

    environment {
        APP_NAME = 'secure-flask-app'
        APP_PORT = '3000'
        COVERAGE_MIN = '80'
        PYTHON_IMAGE = 'python:3.12-slim'
        TRIVY_CACHE_DIR = '/var/lib/jenkins/.cache/trivy'
        TRIVY_TIMEOUT = '5m'
        USE_ECR = 'true'
        ECR_PUSH_LATEST = 'false'
        AWS_REGION = 'eu-west-1'
        REGISTRY = '414392949441.dkr.ecr.eu-west-1.amazonaws.com'
        IMAGE_NAME = "${REGISTRY}/${APP_NAME}"
        DEPLOY_CONTAINER = 'secure-flask-app'
        EC2_HOST = 'ec2-34-240-74-180.eu-west-1.compute.amazonaws.com'
        EC2_USER = 'ec2-user'
        EC2_SSH_CREDENTIALS_ID = 'ec2_ssh'
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

        stage('Install / Build') {
            steps {
                sh '''
                    set -euo pipefail
                    docker run --rm \
                      -u "$(id -u):$(id -g)" \
                      -v "$PWD:/workspace" \
                      -w /workspace \
                      "${PYTHON_IMAGE}" \
                      bash -lc '
                        python -m venv .venv
                        . .venv/bin/activate
                        pip install --upgrade pip
                        pip install -r app/requirements.txt -r app/requirements-dev.txt
                        pip check
                      '
                '''
            }
        }

        stage('Initialize') {
            steps {
                sh '''
                    set -euo pipefail
                    if [ "${USE_ECR}" = "true" ]; then
                      command -v aws >/dev/null 2>&1 || { echo "aws CLI is required for ECR"; exit 1; }
                    fi
                '''
            }
        }

        stage('Test') {
            steps {
                sh '''
                    set -euo pipefail
                    docker run --rm \
                      -u "$(id -u):$(id -g)" \
                      -v "$PWD:/workspace" \
                      -w /workspace \
                      "${PYTHON_IMAGE}" \
                      bash -lc '
                        . .venv/bin/activate
                        export PYTHONPATH=/workspace
                        pytest -q --cov=app --cov-report=xml --cov-fail-under='"${COVERAGE_MIN}"'
                      '
                '''
            }
        }

        stage('Security Gates') {
            steps {
                sh '''
                    set -euo pipefail
                    docker run --rm \
                      -u "$(id -u):$(id -g)" \
                      -v "$PWD:/workspace" \
                      -w /workspace \
                      "${PYTHON_IMAGE}" \
                      bash -lc '
                        . .venv/bin/activate
                        bandit -q -r app
                        pip-audit -r app/requirements.txt
                      '
                    # Trivy checks temporarily disabled.
                    # if ! command -v trivy >/dev/null 2>&1; then
                    #     echo "Trivy not found on agent. Install Trivy CLI." >&2
                    #     exit 1
                    # fi
                    # mkdir -p "${TRIVY_CACHE_DIR}"
                    # trivy image --cache-dir "${TRIVY_CACHE_DIR}" --download-db-only
                    # trivy fs \
                    #   --cache-dir "${TRIVY_CACHE_DIR}" \
                    #   --timeout "${TRIVY_TIMEOUT}" \
                    #   --scanners vuln,misconfig \
                    #   --severity HIGH,CRITICAL \
                    #   --exit-code 1 \
                    #   app app/Dockerfile
                    # trivy fs \
                    #   --cache-dir "${TRIVY_CACHE_DIR}" \
                    #   --timeout "${TRIVY_TIMEOUT}" \
                    #   --scanners secret \
                    #   --severity HIGH,CRITICAL \
                    #   --exit-code 1 \
                    #   --skip-dirs .git \
                    #   --skip-dirs .venv \
                    #   --skip-dirs .pytest_cache \
                    #   app tests Jenkinsfile README.md runbook.md
                '''
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
                    if (env.USE_ECR == 'true') {
                        sh '''
                            set -euo pipefail
                            aws ecr get-login-password --region "${AWS_REGION}" | docker login --username AWS --password-stdin "${REGISTRY}"
                            docker push ${IMAGE_NAME}:${BUILD_NUMBER}
                            if [ "${ECR_PUSH_LATEST}" = "true" ]; then
                              docker push ${IMAGE_NAME}:latest
                            else
                              echo "Skipping latest tag push for immutable ECR repository."
                            fi
                            docker logout "${REGISTRY}"
                        '''
                    } else {
                        withCredentials([usernamePassword(credentialsId: 'registry_creds', usernameVariable: 'REGISTRY_USER', passwordVariable: 'REGISTRY_PASS')]) {
                            sh '''
                                set -euo pipefail
                                echo "${REGISTRY_PASS}" | docker login -u "${REGISTRY_USER}" --password-stdin "${REGISTRY}"
                                docker push ${IMAGE_NAME}:${BUILD_NUMBER}
                                docker push ${IMAGE_NAME}:latest
                                docker logout "${REGISTRY}"
                            '''
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
