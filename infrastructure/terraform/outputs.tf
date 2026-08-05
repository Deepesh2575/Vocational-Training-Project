output "cluster_endpoint" {
  description = "Endpoint for EKS control plane."
  value       = module.eks.cluster_endpoint
}

output "cluster_security_group_id" {
  description = "Security group ID attached to the EKS cluster."
  value       = module.eks.cluster_security_group_id
}

output "region" {
  description = "AWS region."
  value       = var.aws_region
}

output "configure_kubectl" {
  description = "Command to configure kubectl."
  value       = "aws eks --region ${var.aws_region} update-kubeconfig --name ${var.cluster_name}"
}
