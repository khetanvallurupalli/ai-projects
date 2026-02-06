# EKS + Kuma + CFK Infrastructure

Production-ready Pulumi (Python) infrastructure for deploying EKS clusters with Kuma service mesh, Confluent for Kubernetes (CFK), and comprehensive observability stack.

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              AWS Account                                     │
│  ┌────────────────────────────────────────────────────────────────────────┐ │
│  │                         Existing VPC                                    │ │
│  │  ┌──────────────────────────────────────────────────────────────────┐  │ │
│  │  │                        EKS Cluster                                │  │ │
│  │  │                                                                   │  │ │
│  │  │  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────────┐   │  │ │
│  │  │  │ kuma-system │  │ confluent   │  │     observability       │   │  │ │
│  │  │  │             │  │             │  │                         │   │  │ │
│  │  │  │ Kuma CP     │  │ CFK         │  │ Prometheus  Jaeger      │   │  │ │
│  │  │  │ Zone Ingress│  │ Kafka       │  │                         │   │  │ │
│  │  │  │ Zone Egress │  │ Connect     │  │                         │   │  │ │
│  │  │  └─────────────┘  └─────────────┘  └─────────────────────────┘   │  │ │
│  │  │                                                                   │  │ │
│  │  │  ┌─────────────────────────────────────────────────────────────┐ │  │ │
│  │  │  │                    Application Namespaces                   │ │  │ │
│  │  │  │  ┌─────────┐  ┌─────────┐  ┌─────────┐  ┌─────────┐        │ │  │ │
│  │  │  │  │frontend │  │ backend │  │   api   │  │  nginx  │        │ │  │ │
│  │  │  │  │ + sidecar│ │ + sidecar│ │ + sidecar│ │ + sidecar│       │ │  │ │
│  │  │  │  └─────────┘  └─────────┘  └─────────┘  └─────────┘        │ │  │ │
│  │  │  └─────────────────────────────────────────────────────────────┘ │  │ │
│  │  └──────────────────────────────────────────────────────────────────┘  │ │
│  └────────────────────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────────────────────┘
```

## Project Structure

```
.
├── bootstrap/              # S3 state bucket setup (one-time)
│   ├── Pulumi.yaml
│   ├── Pulumi.dev.yaml
│   ├── Pulumi.prod.yaml
│   ├── requirements.txt
│   └── __main__.py
│
├── infra/                  # Core EKS + Kuma + CFK infrastructure
│   ├── Pulumi.yaml
│   ├── Pulumi.dev.yaml
│   ├── Pulumi.prod.yaml
│   ├── requirements.txt
│   ├── config.py
│   ├── __main__.py
│   └── components/
│       ├── vpc.py          # Existing VPC lookup
│       ├── eks_cluster.py  # EKS cluster + node groups
│       ├── irsa.py         # IAM Roles for Service Accounts
│       ├── eks_addons.py   # CoreDNS, VPC CNI, EBS CSI
│       ├── kuma.py         # Kuma control plane
│       ├── cfk.py          # Confluent for Kubernetes
│       └── connectors.py   # Kafka Connect connectors
│
├── kuma-orchestration/     # Kuma policies and multi-zone setup
│   ├── Pulumi.yaml
│   ├── Pulumi.dev.yaml
│   ├── Pulumi.prod.yaml
│   ├── requirements.txt
│   ├── config.py
│   ├── __main__.py
│   ├── README.md
│   └── components/
│       ├── cluster_ref.py       # Stack reference to infra
│       ├── kuma_global_cp.py    # Global control plane
│       ├── kuma_zone_cp.py      # Zone control plane
│       ├── zone_resources.py    # ZoneIngress/Egress
│       ├── traffic_routing.py   # MeshHTTPRoute/TCPRoute
│       ├── traffic_permissions.py
│       ├── rate_limit.py
│       ├── circuit_breaker.py
│       ├── resilience.py        # Timeout + Retry
│       ├── fault_injection.py   # Dev only
│       ├── observability.py     # AccessLog/Metric/Trace
│       └── observability_stack.py  # Prometheus + Jaeger
│
├── examples/               # Example applications
│   └── nginx-kuma-demo/    # Nginx with Kuma service mesh
│
└── .github/workflows/      # CI/CD pipelines
    ├── infra-preview.yml   # Preview on PRs
    └── infra-deploy.yml    # Deploy on merge
```

## Quick Start

### Prerequisites

- AWS CLI configured with appropriate credentials
- Pulumi CLI installed (`curl -fsSL https://get.pulumi.com | sh`)
- Python 3.8+
- kubectl
- Existing VPC with public/private subnets

### 1. Bootstrap State Backend (One-time)

```bash
cd bootstrap
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt

pulumi login --local
pulumi stack init dev
pulumi up --stack dev
```

Note the S3 bucket name from the output.

### 2. Deploy Infrastructure

```bash
cd infra
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt

# Login to S3 backend
pulumi login s3://<bucket-name-from-bootstrap>

# Set required config
pulumi stack init dev
pulumi config set aws:region us-west-2
pulumi config set vpcId vpc-xxxxxxxxx
pulumi config set publicSubnetIds '["subnet-xxx", "subnet-yyy"]'
pulumi config set privateSubnetIds '["subnet-aaa", "subnet-bbb"]'

# Set secrets
pulumi config set --secret confluentCloudApiKey <value>
pulumi config set --secret confluentCloudApiSecret <value>

# Deploy
pulumi up --stack dev
```

### 3. Deploy Kuma Policies

```bash
cd kuma-orchestration
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt

pulumi login s3://<bucket-name>
pulumi stack init dev
pulumi config set infraStackName organization/infra/dev

pulumi up --stack dev
```

### 4. Deploy Example App

```bash
# Get kubeconfig
aws eks update-kubeconfig --name <cluster-name> --region us-west-2

# Deploy nginx example
kubectl apply -f examples/nginx-kuma-demo/
```

## Environment Differences

| Setting | Dev | Prod |
|---------|-----|------|
| **EKS** | | |
| Instance type | t3.large | m5.xlarge |
| Node count | 2 (1-5) | 3 (3-10) |
| Public endpoint | Enabled | Disabled |
| **Kuma** | | |
| Traffic permission | Allow | Deny |
| Fault injection | Enabled | Disabled |
| Trace sample rate | 50% | 1% |
| **CFK** | | |
| Connect replicas | 1 | 2 |

## Kuma Service Mesh Features

This project deploys a comprehensive Kuma service mesh with:

- **mTLS**: Automatic mutual TLS between all services
- **Traffic Routing**: HTTP and TCP routing policies per service
- **Traffic Permissions**: Zero-trust networking (deny by default in prod)
- **Rate Limiting**: Per-service rate limits with 429 responses
- **Circuit Breaker**: Connection limits and outlier detection
- **Resilience**: Configurable timeouts and retries
- **Fault Injection**: Testing failures in dev environment
- **Observability**: Structured logging, Prometheus metrics, distributed tracing

## CI/CD

### Pull Requests

`infra-preview.yml` runs on PRs:
- Runs `pulumi preview` for both dev and prod stacks
- Comments the plan on the PR

### Merge to Main

`infra-deploy.yml` runs on merge:
1. Deploys to dev environment
2. Waits for GitHub Environment approval
3. Deploys to prod environment

### Required GitHub Secrets

| Secret | Description |
|--------|-------------|
| `PULUMI_CONFIG_PASSPHRASE` | Passphrase for secret encryption |
| `PULUMI_STATE_BUCKET` | S3 bucket for state |
| `AWS_DEV_ROLE_ARN` | OIDC role for dev account |
| `AWS_PROD_ROLE_ARN` | OIDC role for prod account |

## Verification Commands

```bash
# Check EKS cluster
kubectl get nodes

# Check Kuma
kubectl get mesh -A
kubectl get pods -n kuma-system

# Check policies
kubectl get meshtrafficpermission,meshratelimit,meshcircuitbreaker -n kuma-system

# Check observability
kubectl get pods -n observability

# Check CFK
kubectl get pods -n confluent
kubectl get kafkaconnect -n confluent
```

## Adding a New Service

1. Deploy your service with Kuma sidecar injection:

```yaml
apiVersion: v1
kind: Namespace
metadata:
  name: my-app
  labels:
    kuma.io/sidecar-injection: enabled
---
apiVersion: apps/v1
kind: Deployment
metadata:
  name: my-service
  namespace: my-app
spec:
  # ... your deployment spec
```

2. Add to managed services in `kuma-orchestration/Pulumi.dev.yaml`:

```yaml
kuma:managedServices:
  - frontend
  - backend
  - my-service  # Add here
```

3. Run `pulumi up` to apply policies.

## License

MIT
