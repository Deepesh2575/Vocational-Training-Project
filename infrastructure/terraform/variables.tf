variable "aws_region" {
  description = "AWS region to deploy the infrastructure."
  type        = string
  default     = "us-east-1"
}

variable "cluster_name" {
  description = "Name of the EKS cluster."
  type        = string
  default     = "decentralized-compute-cluster"
}

variable "max_worker_nodes" {
  description = "Maximum number of instances in the worker node group for auto-scaling."
  type        = number
  default     = 10
}
