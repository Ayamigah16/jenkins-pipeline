# Jenkins LTS CI/CD Pipeline (DevSecOps)

## Overview
This repository delivers a production-ready CI/CD pipeline for a containerized Flask application. The pipeline builds, tests, scans, pushes, and deploys the image to an Amazon Linux 2 EC2 host with rollback safety and post-deployment validation.

## Repository Layout
- `app` Flask application and Dockerfile
- `tests` Pytest unit tests
- `Jenkinsfile` Declarative CI/CD pipeline
- `runbook.md` Operational runbook
- `screenshots` Evidence placeholders

## Application Setup
```bash
python -m venv .venv
. .venv/bin/activate
pip install -r app/requirements.txt -r app/requirements-dev.txt
pytest -q --cov=app --cov-fail-under=80
python app/app.py
```

Environment variables:
- `APP_HOST` default `0.0.0.0`
- `APP_PORT` default `3000`
- `ENVIRONMENT` default `production`
- `DEBUG` default `false`
- `APP_NAME` default `secure-flask-app`

Health endpoint:
- `GET /health`

## Jenkins Configuration
Required plugins:
- Pipeline
- Git
- Credentials Binding
- Docker Pipeline
- SSH Agent
- Workspace Cleanup
- OWASP Dependency Check (optional)
- Trivy (CLI)

Credentials in Jenkins:
- `git_credentials` for GitHub
- `registry_creds` for Docker registry
- `ec2_ssh` for EC2 SSH access

Update the following in `Jenkinsfile`:
- `REGISTRY` to your Docker Hub namespace or ECR registry
- `IMAGE_NAME` is derived from `REGISTRY` and `APP_NAME`
- `EC2_HOST` and `EC2_USER`

## Deployment Architecture
- Jenkins agent builds and scans the image.
- Registry stores versioned and `latest` tags.
- EC2 pulls the image, stages it on port `3001`, validates `/health`, then switches traffic to port `80`.

## Security Controls
- Dependency scan with `pip-audit`
- Static analysis with `bandit`
- Secrets and config scan with `trivy fs`
- Image scan with `trivy image`
- Non-root container user, read-only filesystem, and dropped capabilities

## Rollback Process
- If staging health checks fail, the staging container is removed and the active container stays.
- If production health checks fail after switch, the previous image is restarted automatically.

## Verification Checklist
- Jenkins pipeline completes all stages
- Image is visible in your registry with `latest` and build tags
- EC2 container running and serving `http://<EC2_PUBLIC_DNS>/health`
