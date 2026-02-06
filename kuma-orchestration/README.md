# Kuma Orchestration

Pulumi (Python) project that deploys comprehensive Kuma service mesh policies on an existing EKS cluster provisioned by the `infra/` project. Includes multi-zone federation, full policy suite (traffic, security, resilience, observability), and Prometheus/Jaeger stack.

## Prerequisites

- Pulumi CLI installed
- Python 3.8+
- `infra/` stack deployed (provides EKS cluster)
- AWS credentials configured

## Project Structure

```
kuma-orchestration/
├── Pulumi.yaml                    # Project definition
├── Pulumi.dev.yaml                # Dev stack config
├── Pulumi.prod.yaml               # Prod stack config
├── requirements.txt               # Python dependencies
├── __main__.py                    # Entrypoint - wires all components
├── config.py                      # Typed dataclass config loader
├── README.md                      # This file
└── components/
    ├── __init__.py                # Public re-exports
    ├── cluster_ref.py             # Stack reference to read EKS outputs
    ├── kuma_global_cp.py          # Global control plane (Helm) + Mesh CRD
    ├── kuma_zone_cp.py            # Zone control plane for multi-zone
    ├── zone_resources.py          # ZoneIngress + ZoneEgress
    ├── traffic_routing.py         # MeshHTTPRoute + MeshTCPRoute
    ├── traffic_permissions.py     # MeshTrafficPermission
    ├── rate_limit.py              # MeshRateLimit
    ├── circuit_breaker.py         # MeshCircuitBreaker
    ├── resilience.py              # MeshRetry + MeshTimeout
    ├── fault_injection.py         # MeshFaultInjection (dev only)
    ├── observability.py           # MeshAccessLog + MeshMetric + MeshTrace
    └── observability_stack.py     # Prometheus + Jaeger Helm releases
```

## Commands

```bash
# Setup
cd kuma-orchestration
python -m venv venv
source venv/bin/activate  # or venv\Scripts\activate on Windows
pip install -r requirements.txt

# Login to Pulumi state backend
pulumi login s3://<bucket-name>

# Initialize stack
pulumi stack init dev

# Preview changes
pulumi preview --stack dev

# Deploy
pulumi up --stack dev

# Deploy to production
pulumi up --stack prod
```

## Configuration Reference

| Config Key | Type | Default | Description |
|------------|------|---------|-------------|
| `infraStackName` | string | required | Stack reference to infra project |
| `kuma:version` | string | 2.6.0 | Kuma version |
| `kuma:mode` | string | zone | Control plane mode (zone/global) |
| `kuma:namespace` | string | kuma-system | Kuma namespace |
| `kuma:zoneName` | string | {env}-zone | Zone name |
| `kuma:meshName` | string | default | Mesh name |
| `kuma:mtlsEnabled` | bool | true | Enable mTLS |
| `kuma:httpRequestTimeout` | int | 15 | HTTP timeout (seconds) |
| `kuma:retryAttempts` | int | 3 | Retry attempts |
| `kuma:rateLimitRps` | int | 100 | Rate limit RPS |
| `kuma:circuitBreakerMaxConnections` | int | 512 | Max connections |
| `kuma:tracingBackend` | string | jaeger | Tracing backend (jaeger/datadog) |
| `kuma:traceSampleRate` | float | 0.5 | Trace sample rate (0-1) |
| `kuma:faultInjectionEnabled` | bool | true | Enable fault injection |
| `kuma:trafficPermissionDefault` | string | Allow | Default permission (Allow/Deny) |
| `kuma:managedServices` | list | [] | Services to apply policies to |

## Dev vs Prod Differences

| Setting | Dev | Prod |
|---------|-----|------|
| Traffic permission default | Allow | Deny |
| Fault injection | Enabled | Disabled |
| Trace sample rate | 50% | 1% |
| Tracing backend | Jaeger | Datadog |
| HTTP timeout | 30s | 15s |
| Rate limit RPS | 100 | 1000 |
| Circuit breaker max | 512 | 4096 |
| Jaeger storage | In-memory | Elasticsearch |

## Dependency Graph

```
ClusterReference
       │
       ▼
KumaControlPlane ──────► ObservabilityStack
       │
       ▼
ZoneResources
       │
       ├──► TrafficRouting
       ├──► TrafficPermissions
       ├──► RateLimiting
       ├──► CircuitBreaker
       ├──► Resilience
       └──► FaultInjection
                 │
                 ▼
       ObservabilityPolicies
```

## Adding a New Service

1. Add the service name to `kuma:managedServices` in the stack config:

```yaml
kuma:managedServices:
  - frontend
  - backend
  - api-gateway
  - my-new-service  # Add here
```

2. Run `pulumi up` - all policies will be applied to the new service.

## Adding Custom Policies

Create a new component in `components/` following the pattern:

```python
from typing import Optional
import pulumi_kubernetes as k8s
from pulumi import ComponentResource, ResourceOptions
from config import KumaConfig

class MyCustomPolicy(ComponentResource):
    def __init__(
        self,
        name: str,
        config: KumaConfig,
        k8s_provider: k8s.Provider,
        opts: Optional[ResourceOptions] = None,
    ):
        super().__init__("kuma:orchestration:MyCustomPolicy", name, None, opts)

        # Create your CRDs here
        self.policy = k8s.apiextensions.CustomResource(
            f"{name}-my-policy",
            api_version="kuma.io/v1alpha1",
            kind="MyPolicyKind",
            metadata=k8s.meta.v1.ObjectMetaArgs(
                name="my-policy",
                namespace=config.kuma_namespace,
            ),
            spec={
                # Policy spec
            },
            opts=ResourceOptions(parent=self, provider=k8s_provider),
        )

        self.register_outputs({"policy_name": self.policy.metadata.name})
```

Then wire it in `__main__.py`.

## API Version Reference

| CRD | API Version |
|-----|-------------|
| Mesh, ZoneIngress, ZoneEgress | `kuma.io/v1alpha1` |
| MeshTrafficPermission, MeshRateLimit, MeshCircuitBreaker | `kuma.io/v1alpha1` |
| MeshFaultInjection, MeshAccessLog, MeshMetric, MeshTrace | `kuma.io/v1alpha1` |
| MeshHTTPRoute, MeshTCPRoute, MeshTimeout, MeshRetry | `kuma.io/v2alpha1` |

## Verification

After deployment, verify resources:

```bash
# Check Mesh
kubectl get mesh -A

# Check policies
kubectl get meshtrafficpermission,meshratelimit,meshcircuitbreaker -n kuma-system

# Check observability
kubectl get pods -n observability

# Check Kuma CP pods
kubectl get pods -n kuma-system

# Check zone resources
kubectl get zoneingress,zoneegress -n kuma-system
```

## Troubleshooting

**Stack reference not found:**
Ensure the `infraStackName` matches your infra project stack (e.g., `organization/infra/dev`).

**Helm release stuck:**
Check if the namespace exists and Helm can connect to the cluster.

**CRD not created:**
Ensure Kuma control plane is running before policies are applied (dependency chain).

**Tracing not working:**
Verify Jaeger/Datadog pods are running in the observability namespace.
