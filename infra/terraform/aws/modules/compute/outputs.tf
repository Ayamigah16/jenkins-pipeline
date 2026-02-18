output "jenkins_public_ip" {
  value = aws_instance.jenkins.public_ip
}

output "jenkins_public_dns" {
  value = aws_instance.jenkins.public_dns
}

output "deploy_public_ip" {
  value = aws_instance.deploy.public_ip
}

output "deploy_public_dns" {
  value = aws_instance.deploy.public_dns
}
