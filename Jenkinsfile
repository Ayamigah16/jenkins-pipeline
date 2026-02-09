pipeline {
    agent any

    options {
        timestamps()
        ansiColor('xterm')
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
        REGISTRY = 'docker.io/your-dockerhub-user'
        IMAGE_NAME = "${REGISTRY}/${APP_NAME}"
        DEPLOY_CONTAINER = 'secure-flask-app'
        EC2_HOST = 'YOUR_EC2_PUBLIC_DNS'
        EC2_USER = 'ec2-user'
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
                    python -m venv .venv
                    . .venv/bin/activate
                    pip install --upgrade pip
                    pip install -r app/requirements.txt -r app/requirements-dev.txt
                    pip check
                '''
            }
        }

        stage('Test') {
            steps {
                sh '''
                    set -euo pipefail
                    . .venv/bin/activate
                    pytest -q --cov=app --cov-report=xml --cov-fail-under=${COVERAGE_MIN}
                '''
            }
        }

        stage('Security Gates') {
            steps {
                sh '''
                    set -euo pipefail
                    . .venv/bin/activate
                    bandit -q -r app
                    pip-audit -r app/requirements.txt
                    if ! command -v trivy >/dev/null 2>&1; then
                        echo "Trivy not found on agent. Install Trivy CLI." >&2
                        exit 1
                    fi
                    trivy fs --scanners vuln,secret,config --severity HIGH,CRITICAL --exit-code 1 .
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
                    trivy image --severity HIGH,CRITICAL --exit-code 1 ${IMAGE_NAME}:${BUILD_NUMBER}
                '''
            }
        }

        stage('Push Image') {
            steps {
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

        stage('Deploy to EC2') {
            steps {
                sshagent(credentials: ['ec2_ssh']) {
                    sh '''
                        set -euo pipefail
                        ssh -o StrictHostKeyChecking=no ${EC2_USER}@${EC2_HOST} \
                          "IMAGE_NAME='${IMAGE_NAME}:${BUILD_NUMBER}' REGISTRY='${REGISTRY}' APP_NAME='${APP_NAME}' DEPLOY_CONTAINER='${DEPLOY_CONTAINER}' bash -s" <<'EOF'
                        set -euo pipefail
                        APP_PORT=3000
                        ACTIVE_CONTAINER="${DEPLOY_CONTAINER}"
                        STAGING_CONTAINER="${DEPLOY_CONTAINER}-staging"

                        docker pull "${IMAGE_NAME}"

                        if docker ps --format '{{.Names}}' | grep -q "^${ACTIVE_CONTAINER}$"; then
                          OLD_IMAGE=$(docker inspect -f '{{.Config.Image}}' "${ACTIVE_CONTAINER}")
                        else
                          OLD_IMAGE=""
                        fi

                        if docker ps --format '{{.Names}}' | grep -q "^${STAGING_CONTAINER}$"; then
                          docker rm -f "${STAGING_CONTAINER}"
                        fi

                        docker run -d --name "${STAGING_CONTAINER}" -p 3001:${APP_PORT} \
                          --read-only \
                          --tmpfs /tmp:size=10M,mode=1777 \
                          --security-opt=no-new-privileges:true \
                          --cap-drop=ALL \
                          -e ENVIRONMENT=production \
                          -e DEBUG=false \
                          "${IMAGE_NAME}"

                        for i in {1..10}; do
                          if curl -fsS "http://localhost:3001/health" >/dev/null 2>&1; then
                            break
                          fi
                          sleep 2
                        done

                        if ! curl -fsS "http://localhost:3001/health" >/dev/null 2>&1; then
                          docker logs "${STAGING_CONTAINER}" || true
                          docker rm -f "${STAGING_CONTAINER}" || true
                          exit 1
                        fi

                        if docker ps --format '{{.Names}}' | grep -q "^${ACTIVE_CONTAINER}$"; then
                          docker rm -f "${ACTIVE_CONTAINER}"
                        fi

                        docker run -d --name "${ACTIVE_CONTAINER}" -p 80:${APP_PORT} \
                          --read-only \
                          --tmpfs /tmp:size=10M,mode=1777 \
                          --security-opt=no-new-privileges:true \
                          --cap-drop=ALL \
                          -e ENVIRONMENT=production \
                          -e DEBUG=false \
                          "${IMAGE_NAME}"

                        docker rm -f "${STAGING_CONTAINER}" || true

                        if ! curl -fsS "http://localhost/health" >/dev/null 2>&1; then
                          docker rm -f "${ACTIVE_CONTAINER}" || true
                          if [ -n "${OLD_IMAGE}" ]; then
                            docker run -d --name "${ACTIVE_CONTAINER}" -p 80:${APP_PORT} \
                              --read-only \
                              --tmpfs /tmp:size=10M,mode=1777 \
                              --security-opt=no-new-privileges:true \
                              --cap-drop=ALL \
                              -e ENVIRONMENT=production \
                              -e DEBUG=false \
                              "${OLD_IMAGE}"
                          fi
                          exit 1
                        fi

                        docker container prune -f
                        KEEP=3
                        docker images --format '{{.Repository}}:{{.Tag}} {{.ID}} {{.CreatedAt}}' \
                          | grep "^${REGISTRY}/${APP_NAME}:" \
                          | tail -n +$((KEEP+1)) \
                          | awk '{print $2}' \
                          | xargs -r docker rmi -f || true
                        EOF
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
