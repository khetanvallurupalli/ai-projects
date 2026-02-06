# Kuma Orchestration

Production-ready Pulumi (Python) project for deploying Kuma service mesh with multi-cluster support, cross-cluster mTLS, and comprehensive policy management.

## Features

- **Multi-Cluster Support**: EKS, AKS, AKS Local (on-premises), GKE, K3s, KIND
- **Cross-Cluster mTLS**: Automatic certificate management with rotation
- **Namespace-Level Cross-Cluster Access**: Enable multi-cluster access per namespace, with optional service-name granularity
- **Locality-Aware Load Balancing**: Prefer local zone, failover to remote
- **Complete Policy Suite**: Traffic routing, permissions, rate limiting, circuit breaker, resilience
- **Observability Stack**: Prometheus + Jaeger/Datadog integration
- **Zero-Trust Networking**: Deny by default in production

## Architecture

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                           Multi-Cluster Kuma Federation                          │
├─────────────────────────────────────────────────────────────────────────────────┤
│                                                                                  │
│  ┌─────────────────────┐                      ┌─────────────────────┐           │
│  │   EKS Cluster       │                      │   AKS Cluster       │           │
│  │   (Global CP)       │◄────── KDS ─────────►│   (Zone CP)         │           │
│  │                     │      (mTLS)          │                     │           │
│  │  ┌───────────────┐  │                      │  ┌───────────────┐  │           │
│  │  │ Global CP     │  │                      │  │ Zone CP       │  │           │
│  │  │ - Mesh        │  │                      │  │ - Zone Ingress│  │           │
│  │  │ - Policies    │  │                      │  │ - Zone Egress │  │           │
│  │  │ - CA          │  │                      │  │ - Local Proxy │  │           │
│  │  └───────────────┘  │                      │  └───────────────┘  │           │
│  │         │           │                      │         │           │           │
│  │  ┌──────▼────────┐  │                      │  ┌──────▼────────┐  │           │
│  │  │ Zone Ingress  │◄─┼──────────────────────┼──│ Zone Egress   │  │           │
│  │  │ Zone Egress   │──┼──────────────────────┼─►│ Zone Ingress  │  │           │
│  │  └───────────────┘  │                      │  └───────────────┘  │           │
│  │         │           │                      │         │           │           │
│  │  ┌──────▼────────┐  │                      │  ┌──────▼────────┐  │           │
│  │  │  App Pods     │  │                      │  │  App Pods     │  │           │
│  │  │  + Sidecar    │◄─┼─────── mTLS ─────────┼─►│  + Sidecar    │  │           │
│  │  └───────────────┘  │                      │  └───────────────┘  │           │
│  └─────────────────────┘                      └─────────────────────┘           │
│                                                                                  │
│  ┌─────────────────────┐                      ┌─────────────────────┐           │
│  │   AKS Local         │                      │   GKE Cluster       │           │
│  │   (On-Premises)     │◄────── KDS ─────────►│   (Zone CP)         │           │
│  │                     │                      │                     │           │
│  └─────────────────────┘                      └─────────────────────┘           │
│                                                                                  │
└─────────────────────────────────────────────────────────────────────────────────┘
```

## Quick Start

### Prerequisites

- Pulumi CLI installed
- Python 3.8+
- kubectl configured
- Cloud credentials (AWS/Azure/GCP)

### Single Cluster Deployment

```bash
cd kuma-orchestration
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt

pulumi login s3://<bucket-name>
pulumi stack init dev

# Simple single-cluster config
pulumi config set kuma-orchestration:infraStackName organization/infra/dev

pulumi up --stack dev
```

### Multi-Cluster Deployment

See [MULTI_CLUSTER.md](./MULTI_CLUSTER.md) for detailed multi-cluster setup.

```bash
# Deploy to each cluster
for cluster in eks-dev aks-dev; do
  pulumi config set cluster:currentCluster $cluster
  pulumi up --yes
done
```

## Project Structure

```
kuma-orchestration/
├── Pulumi.yaml                     # Project definition
├── Pulumi.dev.yaml                 # Dev stack (multi-cluster example)
├── Pulumi.prod.yaml                # Prod stack (multi-region)
├── requirements.txt                # Python dependencies
├── config.py                       # Multi-cluster config loader
├── __main__.py                     # Main entrypoint
├── README.md                       # This file
├── MULTI_CLUSTER.md                # Multi-cluster guide
└── components/
    ├── __init__.py                 # Public exports
    ├── cluster_ref.py              # Legacy single-cluster reference
    ├── cluster_providers.py        # Multi-cluster provider factory
    ├── kuma_global_cp.py           # Global control plane
    ├── kuma_zone_cp.py             # Zone control plane
    ├── zone_resources.py           # ZoneIngress/Egress
    ├── cross_cluster_policies.py   # Cross-cluster mTLS + policies
    ├── traffic_routing.py          # MeshHTTPRoute/TCPRoute
    ├── traffic_permissions.py      # MeshTrafficPermission
    ├── rate_limit.py               # MeshRateLimit
    ├── circuit_breaker.py          # MeshCircuitBreaker
    ├── resilience.py               # MeshTimeout/Retry
    ├── fault_injection.py          # MeshFaultInjection
    ├── observability.py            # AccessLog/Metric/Trace
    └── observability_stack.py      # Prometheus + Jaeger
```

## Configuration Reference

### Cluster Configuration

| Key | Type | Description |
|-----|------|-------------|
| `cluster:currentCluster` | string | Active cluster for this deployment |
| `cluster:clusters` | list | List of cluster configurations |
| `cluster:clusters[].name` | string | Unique cluster identifier |
| `cluster:clusters[].type` | enum | eks, aks, aks-local, gke, k3s, kind |
| `cluster:clusters[].zoneName` | string | Kuma zone name |
| `cluster:clusters[].region` | string | Cloud region |
| `cluster:clusters[].infraStackName` | string | Pulumi stack for kubeconfig |
| `cluster:clusters[].isGlobalCpCluster` | bool | Hosts global control plane |

### Cross-Cluster Configuration

| Key | Type | Default | Description |
|-----|------|---------|-------------|
| `crossCluster:enabled` | bool | true | Enable multi-cluster |
| `crossCluster:mtlsMode` | string | strict | mTLS mode (strict/permissive) |
| `crossCluster:caBackend` | string | builtin | CA backend (builtin/vault) |
| `crossCluster:localityAwareLb` | bool | true | Prefer local zone |
| `crossCluster:crossZoneTrafficDefault` | string | Allow | Default cross-zone action |

### Cross-Cluster Namespace Access

Configure which namespaces (and optionally which services) are accessible across clusters:

```yaml
kuma:crossClusterNamespaces:
  # Only specific services in this namespace are accessible cross-cluster
  - namespace: backend-ns
    services:
      - backend
      - api-gateway

  # ALL services in this namespace are accessible cross-cluster
  - namespace: shared-services
```

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `namespace` | string | yes | Kubernetes namespace to enable cross-cluster access for |
| `services` | list | no | Specific service names to expose. If omitted, all services in the namespace are accessible |

- **With `services`**: Policies target each service by `MeshService` (name + namespace) for fine-grained control.
- **Without `services`**: Policies target the entire namespace via `MeshSubset` (`k8s.kuma.io/namespace` tag).

### Policy Configuration

| Key | Type | Default | Description |
|-----|------|---------|-------------|
| `kuma:trafficPermissionDefault` | string | Allow | Default traffic permission |
| `kuma:rateLimitRps` | int | 100 | Rate limit per service |
| `kuma:circuitBreakerMaxConnections` | int | 512 | Max connections |
| `kuma:httpRequestTimeout` | int | 15 | HTTP timeout (seconds) |
| `kuma:retryAttempts` | int | 3 | Retry count |

## Supported Cluster Types

| Type | Value | Description |
|------|-------|-------------|
| Amazon EKS | `eks` | AWS managed Kubernetes |
| Azure AKS | `aks` | Azure managed Kubernetes |
| AKS Local | `aks-local` | Azure Arc-enabled on-premises |
| Google GKE | `gke` | GCP managed Kubernetes |
| K3s | `k3s` | Lightweight Kubernetes |
| KIND | `kind` | Kubernetes in Docker (dev) |
| OpenShift | `openshift` | Red Hat OpenShift |
| Rancher | `rancher` | Rancher managed clusters |

## Dev vs Prod Differences

| Setting | Dev | Prod |
|---------|-----|------|
| Global CP replicas | 1 | 3 |
| Traffic permission default | Allow | Deny |
| Cross-zone traffic default | Allow | Deny |
| Fault injection | Enabled | Disabled |
| Trace sample rate | 50% | 1% |
| Tracing backend | Jaeger | Datadog |
| Rate limit RPS | 100 | 1000 |
| Circuit breaker max | 512 | 4096 |

## Verification

```bash
# Check Kuma installation
kubectl get pods -n kuma-system
kubectl get mesh -A

# Check zone connectivity (multi-cluster)
kubectl get zones -n kuma-system

# Check policies
kubectl get meshtrafficpermission,meshratelimit,meshcircuitbreaker -n kuma-system

# Check cross-cluster namespace policies
kubectl get meshtrafficpermission -n kuma-system -l kuma.io/policy-type=cross-cluster

# Check cross-cluster health checks
kubectl get meshhealthcheck -n kuma-system -l cross-cluster-namespace

# Test cross-cluster call (service in backend-ns namespace)
kubectl exec -n app deployment/client -- curl http://backend.backend-ns.svc.cluster.local
```

## Troubleshooting

### Zone not connecting to Global CP

1. Check KDS connectivity:
```bash
kubectl logs -n kuma-system deployment/kuma-control-plane | grep -i kds
```

2. Verify global address:
```bash
kubectl get svc -n kuma-system kuma-global-zone-sync
```

3. Check certificates:
```bash
kubectl get secrets -n kuma-system | grep tls
```

### Cross-cluster traffic failing

1. Check ZoneIngress/Egress:
```bash
kubectl get zoneingress,zoneegress -n kuma-system
```

2. Verify traffic permissions:
```bash
kubectl get meshtrafficpermission -n kuma-system -o yaml
```

3. Check mTLS status:
```bash
kubectl get mesh default -o yaml | grep -A10 mtls
```

## License

MIT
