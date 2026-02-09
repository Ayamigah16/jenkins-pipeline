# Runbook

## Purpose
Operational guidance for the Jenkins-based CI/CD pipeline and EC2 deployment.

## Pre-Deployment Checklist
- Jenkins LTS installed with required plugins
- Docker Engine installed on Jenkins agent and EC2 host
- Trivy CLI installed on Jenkins agent
- EC2 security group allows SSH (22) and HTTP (80)
- Jenkins credentials configured: `git_credentials`, `registry_creds`, `ec2_ssh`

## Standard Deployment
1. Merge to `main` or `develop`
2. Jenkins pipeline runs build, test, security gates, image build, and push
3. Pipeline deploys to EC2 via SSH and validates `/health`

## Manual Verification
```bash
curl -fsS http://<EC2_PUBLIC_DNS>/health
docker ps
docker logs secure-flask-app --tail=200
```

## Rollback
1. Jenkins automatically restores the previous image on failed post-switch health check
2. If manual rollback is needed:
```bash
docker ps --format '{{.Names}} {{.Image}}'
docker rm -f secure-flask-app
docker run -d --name secure-flask-app -p 80:3000 <previous-image-tag>
```

## Troubleshooting
- `Registry auth failed`: verify `registry_creds` and rate limits
- `Trivy missing`: install Trivy on the Jenkins agent
- `EC2 unreachable`: check security group, public DNS, and SSH key
- `Container crash loop`: inspect logs and health endpoint
- `Port conflict`: verify no other service is bound to port `80`

## Incident Response
- Revoke and rotate any compromised credentials
- Re-run scans to ensure a clean build
- Review Jenkins logs for unauthorized access attempts
