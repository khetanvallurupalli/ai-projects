# EKS + Kuma + CFK Infrastructure

Production-ready Pulumi (Python) infrastructure for deploying multi-cluster Kubernetes with Kuma service mesh, Confluent for Kubernetes (CFK), and comprehensive observability.

## Features

- **Multi-Cloud Support**: AWS EKS, Azure AKS, AKS Local (on-premises), GKE
- **Service Mesh**: Kuma with multi-zone federation and cross-cluster mTLS
- **Streaming Platform**: Confluent for Kubernetes with Kafka Connect
- **Observability**: Prometheus, Jaeger, structured logging
- **Zero-Trust Security**: mTLS everywhere, deny-by-default policies
- **GitOps Ready**: CI/CD with Pulumi and GitHub Actions

## Architecture

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                           Multi-Cluster Architecture                             │
├─────────────────────────────────────────────────────────────────────────────────┤
│                                                                                  │
│  ┌─────────────────────────────────────┐    ┌─────────────────────────────────┐ │
│  │         EKS Cluster (AWS)           │    │       AKS Cluster (Azure)       │ │
│  │                                     │    │                                 │ │
│  │  ┌─────────────┐  ┌──────────────┐  │    │  ┌─────────────┐ ┌───────────┐  │ │
│  │  │ Kuma Global │  │  Confluent   │  │    │  │ Kuma Zone   │ │ App Pods  │  │ │
│  │  │     CP      │  │    CFK       │◄─┼────┼──│     CP      │ │ + Sidecar │  │ │
│  │  └──────┬──────┘  └──────────────┘  │    │  └─────────────┘ └───────────┘  │ │
│  │         │                           │    │                                 │ │
│  │  ┌──────▼──────┐  ┌──────────────┐  │    │  ┌─────────────────────────────┐│ │
│  │  │ Zone Ingress│  │ Prometheus   │  │    │  │     Observability Stack     ││ │
│  │  │ Zone Egress │  │   Jaeger     │  │    │  │   Prometheus + Jaeger       ││ │
│  │  └─────────────┘  └──────────────┘  │    │  └─────────────────────────────┘│ │
│  └─────────────────────────────────────┘    └─────────────────────────────────┘ │
│                        │                                    ▲                    │
│                        │         KDS (mTLS)                 │                    │
│                        └────────────────────────────────────┘                    │
│                                                                                  │
│  ┌─────────────────────────────────────┐    ┌─────────────────────────────────┐ │
│  │      AKS Local (On-Premises)        │    │       GKE Cluster (GCP)         │ │
│  │                                     │    │                                 │ │
│  │  ┌─────────────┐  ┌──────────────┐  │    │  ┌─────────────┐ ┌───────────┐  │ │
│  │  │ Kuma Zone   │  │  App Pods    │  │    │  │ Kuma Zone   │ │ App Pods  │  │ │
│  │  │     CP      │  │  + Sidecar   │◄─┼────┼──│     CP      │ │ + Sidecar │  │ │
│  │  └─────────────┘  └──────────────┘  │    │  └─────────────┘ └───────────┘  │ │
│  └─────────────────────────────────────┘    └─────────────────────────────────┘ │
│                                                                                  │
└─────────────────────────────────────────────────────────────────────────────────┘
```

## Project Structure

```
.
├── bootstrap/                  # S3 state bucket setup (one-time)
│   └── __main__.py
│
├── infra/                      # Core EKS + Kuma + CFK infrastructure
│   ├── __main__.py
│   ├── config.py
│   └── components/
│       ├── vpc.py              # Existing VPC lookup
│       ├── eks_cluster.py      # EKS cluster + node groups
│       ├── eks_addons.py       # CoreDNS, VPC CNI, EBS CSI
│       ├── kuma.py             # Kuma control plane
│       ├── cfk.py              # Confluent for Kubernetes
│       └── connectors.py       # Kafka Connect connectors
│
├── kuma-orchestration/         # Multi-cluster Kuma policies
│   ├── __main__.py
│   ├── config.py               # Multi-cluster config
│   ├── README.md
│   ├── MULTI_CLUSTER.md        # Multi-cluster setup guide
│   └── components/
│       ├── cluster_providers.py    # EKS, AKS, GKE providers
│       ├── kuma_global_cp.py       # Global control plane
│       ├── kuma_zone_cp.py         # Zone control plane
│       ├── cross_cluster_policies.py
│       ├── traffic_routing.py
│       ├── traffic_permissions.py
│       ├── rate_limit.py
│       ├── circuit_breaker.py
│       ├── resilience.py
│       ├── fault_injection.py
│       └── observability_stack.py
│
├── examples/                   # Example applications
│   └── nginx-kuma-demo/        # Nginx with full Kuma policies
│       ├── README.md
│       ├── 01-namespace.yaml
│       ├── 02-nginx.yaml
│       ├── 03-client.yaml
│       └── 04-policies.yaml
│
└── .github/workflows/
    ├── infra-preview.yml       # Preview on PRs
    ├── infra-deploy.yml        # Deploy infra on merge
    └── kuma-deploy.yml         # Deploy Kuma + examples
```

## Quick Start

### Prerequisites

- AWS CLI / Azure CLI / gcloud configured
- Pulumi CLI installed
- Python 3.8+
- kubectl
- Existing VPC (for EKS)

### 1. Bootstrap State Backend

```bash
cd bootstrap
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt

pulumi login --local
pulumi stack init dev
pulumi up --stack dev

# Note the S3 bucket name
```

### 2. Deploy Infrastructure

```bash
cd infra
pip install -r requirements.txt

pulumi login s3://<bucket-name>
pulumi stack init dev

# Configure
pulumi config set aws:region us-west-2
pulumi config set vpcId vpc-xxx
pulumi config set privateSubnetIds '["subnet-a", "subnet-b"]'
pulumi config set --secret confluentCloudApiKey <key>
pulumi config set --secret confluentCloudApiSecret <secret>

pulumi up --stack dev
```

### 3. Deploy Kuma Orchestration

```bash
cd kuma-orchestration
pip install -r requirements.txt

pulumi stack init dev
pulumi config set kuma-orchestration:infraStackName organization/infra/dev

pulumi up --stack dev
```

### 4. Deploy Example App

```bash
aws eks update-kubeconfig --name <cluster-name> --region us-west-2
kubectl apply -f examples/nginx-kuma-demo/

# Test
kubectl exec -it deployment/curl-client -n nginx-demo -c curl -- \
  curl http://nginx.nginx-demo.svc.cluster.local
```

## Multi-Cluster Setup

See [kuma-orchestration/MULTI_CLUSTER.md](./kuma-orchestration/MULTI_CLUSTER.md) for:

- Adding EKS, AKS, AKS Local, GKE clusters
- Cross-cluster mTLS configuration
- Locality-aware load balancing
- Production checklist

### Quick Multi-Cluster Example

```yaml
# kuma-orchestration/Pulumi.dev.yaml
cluster:clusters:
  - name: eks-primary
    type: eks
    zoneName: eks-us-west-2
    infraStackName: organization/infra/dev
    isGlobalCpCluster: true

  - name: aks-secondary
    type: aks
    zoneName: aks-eastus
    infraStackName: organization/aks-infra/dev

crossCluster:enabled: true
crossCluster:mtlsMode: strict
```

## Environment Differences

| Setting | Dev | Prod |
|---------|-----|------|
| **Infrastructure** | | |
| EKS instance type | t3.large | m5.xlarge |
| EKS nodes | 2 (1-5) | 3 (3-10) |
| Global CP replicas | 1 | 3 |
| **Security** | | |
| Traffic permission | Allow | Deny |
| Cross-zone default | Allow | Deny |
| Fault injection | Enabled | Disabled |
| **Observability** | | |
| Trace sample rate | 50% | 1% |
| Tracing backend | Jaeger | Datadog |

## CI/CD

### Pull Requests

- `infra-preview.yml`: Runs `pulumi preview` for both stacks
- Comments plan diff on PR

### Merge to Main

- `infra-deploy.yml`: Deploys infrastructure (dev → prod with approval)
- `kuma-deploy.yml`: Deploys Kuma policies and example apps

### Required Secrets

| Secret | Description |
|--------|-------------|
| `PULUMI_CONFIG_PASSPHRASE` | Secret encryption |
| `PULUMI_STATE_BUCKET` | S3 bucket for state |
| `AWS_DEV_ROLE_ARN` | OIDC role for dev |
| `AWS_PROD_ROLE_ARN` | OIDC role for prod |
| `AZURE_CLIENT_ID` | Azure SP for AKS (optional) |
| `AZURE_TENANT_ID` | Azure tenant (optional) |
| `AZURE_SUBSCRIPTION_ID` | Azure subscription (optional) |

## Verification Commands

```bash
# Check EKS cluster
kubectl get nodes

# Check Kuma
kubectl get mesh -A
kubectl get pods -n kuma-system

# Check multi-zone
kubectl get zones -n kuma-system

# Check policies
kubectl get meshtrafficpermission,meshratelimit,meshcircuitbreaker -n kuma-system

# Check observability
kubectl get pods -n observability

# Check CFK
kubectl get pods -n confluent
kubectl get kafkaconnect -n confluent

# Test cross-cluster (from any cluster)
kubectl exec -n app deployment/client -- curl http://backend.app.svc.cluster.local
```

## Documentation

- [Kuma Orchestration README](./kuma-orchestration/README.md) - Kuma deployment guide
- [Multi-Cluster Guide](./kuma-orchestration/MULTI_CLUSTER.md) - Adding clusters
- [Nginx Demo README](./examples/nginx-kuma-demo/README.md) - Example application

## License

MIT
