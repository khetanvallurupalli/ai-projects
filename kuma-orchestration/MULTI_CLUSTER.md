# Multi-Cluster Kuma Deployment Guide

This guide covers setting up Kuma service mesh across multiple Kubernetes clusters with cross-cluster mTLS, service discovery, and traffic management.

## Table of Contents

1. [Prerequisites](#prerequisites)
2. [Architecture Overview](#architecture-overview)
3. [Adding a New Cluster](#adding-a-new-cluster)
4. [Cross-Cluster Service Access](#cross-cluster-service-access)
5. [Production Checklist](#production-checklist)
6. [Cluster-Specific Setup](#cluster-specific-setup)
7. [Troubleshooting](#troubleshooting)

## Prerequisites

### Required Infrastructure

- **Global CP Cluster**: One cluster must host the Global Control Plane
  - Accessible from all other clusters (LoadBalancer or static IP)
  - Recommended: 3+ nodes for HA
  - Must have stable network connectivity

- **Zone Clusters**: Each additional cluster runs a Zone Control Plane
  - Can be any supported Kubernetes distribution
  - Must be able to reach Global CP on port 5685

### Network Requirements

| Source | Destination | Port | Protocol | Purpose |
|--------|-------------|------|----------|---------|
| Zone CP | Global CP | 5685 | gRPC/TLS | KDS sync |
| Zone Ingress | Zone Egress (other) | 10001 | TCP/mTLS | Cross-zone traffic |
| Zone Egress | Zone Ingress (other) | 10001 | TCP/mTLS | Cross-zone traffic |

### Firewall Rules

```bash
# Global CP cluster - inbound
- Port 5685/TCP from all zone clusters (KDS)

# All clusters - inbound from other zones
- Port 10001/TCP (Zone Ingress)

# All clusters - outbound to other zones
- Port 10001/TCP (Zone Egress destination)
```

## Architecture Overview

### Multi-Zone Federation

```
                                 ┌───────────────────┐
                                 │   Global CP       │
                                 │   (EKS us-west-2) │
                                 │                   │
                                 │  - Mesh Definition│
                                 │  - Policies       │
                                 │  - CA/mTLS        │
                                 └─────────┬─────────┘
                                           │
                    ┌──────────────────────┼──────────────────────┐
                    │                      │                      │
              KDS (5685)             KDS (5685)             KDS (5685)
                    │                      │                      │
           ┌────────▼────────┐    ┌────────▼────────┐    ┌────────▼────────┐
           │   Zone CP       │    │   Zone CP       │    │   Zone CP       │
           │  (AKS eastus)   │    │  (GKE europe)   │    │ (AKS-Local DC1) │
           └────────┬────────┘    └────────┬────────┘    └────────┬────────┘
                    │                      │                      │
           ┌────────▼────────┐    ┌────────▼────────┐    ┌────────▼────────┐
           │ Zone Ingress    │◄───│ Zone Ingress    │◄───│ Zone Ingress    │
           │ Zone Egress     │───►│ Zone Egress     │───►│ Zone Egress     │
           └────────┬────────┘    └────────┬────────┘    └────────┬────────┘
                    │                      │                      │
           ┌────────▼────────┐    ┌────────▼────────┐    ┌────────▼────────┐
           │   App Pods      │    │   App Pods      │    │   App Pods      │
           │   + Sidecars    │    │   + Sidecars    │    │   + Sidecars    │
           └─────────────────┘    └─────────────────┘    └─────────────────┘
```

### Data Flow

1. **KDS (Kuma Discovery Service)**: Zones sync policies and service discovery with Global CP
2. **Zone Ingress**: Receives cross-zone traffic destined for local services
3. **Zone Egress**: Routes outbound traffic to other zones
4. **mTLS**: All cross-zone traffic is encrypted end-to-end

## Adding a New Cluster

### Step 1: Prepare Cluster Configuration

Add the cluster to `Pulumi.dev.yaml` or `Pulumi.prod.yaml`:

```yaml
cluster:clusters:
  # ... existing clusters ...

  # New cluster
  - name: gke-prod-asia
    type: gke
    zoneName: gke-asia-southeast1
    region: asia-southeast1
    infraStackName: organization/gke-infra/prod
    isGlobalCpCluster: false
    zoneIngressEnabled: true
    zoneEgressEnabled: true
    podCidr: "10.100.0.0/16"
    serviceCidr: "10.200.0.0/16"
```

### Step 2: Cluster Type Reference

| Cluster Type | `type` Value | Kubeconfig Source | Notes |
|--------------|--------------|-------------------|-------|
| Amazon EKS | `eks` | `infraStackName` | Use AWS OIDC |
| Azure AKS | `aks` | `infraStackName` | Use Azure OIDC |
| AKS Local | `aks-local` | `kubeconfigSecretName` | On-premises |
| Google GKE | `gke` | `infraStackName` | Use GCP Workload Identity |
| K3s | `k3s` | `kubeconfigSecretName` | Lightweight |
| KIND | `kind` | `kubeconfigSecretName` | Dev only |

### Step 3: For External Clusters (No Pulumi Infra)

If the cluster is not managed by Pulumi, provide kubeconfig via secret:

```bash
# Store kubeconfig as Pulumi secret
pulumi config set --secret kubeconfigGkeAsia "$(cat ~/.kube/gke-asia-config)"
```

Then reference in config:

```yaml
- name: gke-prod-asia
  type: gke
  zoneName: gke-asia-southeast1
  region: asia-southeast1
  kubeconfigSecretName: kubeconfigGkeAsia  # References the secret
  isGlobalCpCluster: false
```

### Step 4: Deploy to New Cluster

```bash
cd kuma-orchestration

# Set target cluster
pulumi config set cluster:currentCluster gke-prod-asia

# Deploy
pulumi up --yes
```

### Step 5: Verify Zone Registration

```bash
# On Global CP cluster
kubectl get zones -n kuma-system

# Expected output:
# NAME                  AGE
# eks-us-west-2         10d
# aks-eastus            5d
# gke-asia-southeast1   1m  <- New zone
```

## Cross-Cluster Service Access

### Enable Cross-Cluster Service

1. Add service to `crossClusterServices` in config:

```yaml
kuma:crossClusterServices:
  - backend
  - api-gateway
  - user-service
  - my-new-service  # Add here
```

2. Deploy the service with sidecar injection:

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: my-new-service
  namespace: app
spec:
  template:
    metadata:
      annotations:
        kuma.io/sidecar-injection: enabled
    spec:
      containers:
        - name: app
          # ...
```

3. Run Pulumi to apply cross-cluster policies:

```bash
pulumi up --yes
```

### Access Service from Another Cluster

Services are automatically discoverable across zones:

```bash
# From any cluster in the mesh
curl http://my-new-service.app.svc.cluster.local

# The sidecar routes to:
# 1. Local zone (if service exists locally) - preferred
# 2. Remote zone via Zone Egress -> Zone Ingress
```

### Locality-Aware Load Balancing

Traffic is routed based on locality:

1. **Same Zone**: Direct pod-to-pod (lowest latency)
2. **Same Region**: Via zone ingress/egress
3. **Cross Region**: Failover when local unavailable

Configure weights:

```yaml
crossCluster:localityAwareLb: true
crossCluster:localityPriorityWeight: 100  # Higher = stronger local preference
```

## Production Checklist

### Security

- [ ] **mTLS Mode**: Set to `strict` in production
- [ ] **Traffic Permissions**: Default to `Deny`
- [ ] **Cross-Zone Default**: Set to `Deny` and explicitly allow
- [ ] **Certificate Rotation**: Configure auto-rotation threshold
- [ ] **Network Policies**: Restrict KDS port access

```yaml
crossCluster:mtlsMode: strict
crossCluster:crossZoneTrafficDefault: Deny
kuma:trafficPermissionDefault: Deny
```

### High Availability

- [ ] **Global CP Replicas**: Minimum 3 for HA
- [ ] **Zone Ingress**: Multiple replicas per zone
- [ ] **External Address**: Use DNS or static IP for Global CP
- [ ] **Pod Disruption Budget**: Set for control plane pods

```yaml
kuma:globalCp:
  replicas: 3
  externalAddress: kuma-global.example.com
  zoneSyncServiceType: LoadBalancer
```

### Networking

- [ ] **Pod CIDR**: Non-overlapping across clusters
- [ ] **Service CIDR**: Non-overlapping across clusters
- [ ] **Firewall Rules**: Allow KDS (5685) and Zone Ingress (10001)
- [ ] **Load Balancer**: NLB recommended for Zone Ingress

### Observability

- [ ] **Distributed Tracing**: Configure across all zones
- [ ] **Metrics Federation**: Aggregate from all clusters
- [ ] **Centralized Logging**: Ship logs to central location

### Disaster Recovery

- [ ] **Global CP Backup**: Regular backup of Mesh configs
- [ ] **Zone Failover**: Test zone failover scenarios
- [ ] **Certificate Backup**: Backup root CA if using custom

## Cluster-Specific Setup

### Amazon EKS

```yaml
- name: eks-prod
  type: eks
  zoneName: eks-us-west-2
  region: us-west-2
  infraStackName: organization/infra/prod
  cloudProviderSettings:
    loadBalancerType: nlb
    loadBalancerScheme: internet-facing
```

Required IAM permissions for the node role:
- `elasticloadbalancing:*` (for NLB)
- `ec2:DescribeSecurityGroups`

### Azure AKS

```yaml
- name: aks-prod
  type: aks
  zoneName: aks-westeurope
  region: westeurope
  infraStackName: organization/aks-infra/prod
  cloudProviderSettings:
    internalLoadBalancer: "false"
```

### AKS Local (On-Premises)

```yaml
- name: aks-local-prod
  type: aks-local
  zoneName: aks-onprem-dc1
  region: onprem-dc1
  kubeconfigSecretName: aks-local-kubeconfig
  cloudProviderSettings:
    apiServerEndpoint: "https://aks-local.internal:6443"
    internalLoadBalancer: "true"
    zoneIngressAddress: "10.50.0.100"  # Static IP for Zone Ingress
```

**Important for on-premises**:
1. Zone Ingress needs a static/known IP for other zones to reach
2. Firewall must allow inbound 10001 from cloud zones
3. Outbound to Global CP port 5685 must be allowed

### Google GKE

```yaml
- name: gke-prod
  type: gke
  zoneName: gke-us-central1
  region: us-central1
  infraStackName: organization/gke-infra/prod
  cloudProviderSettings:
    negEnabled: "true"
```

## Troubleshooting

### Zone Not Appearing in Global CP

1. Check Zone CP logs:
```bash
kubectl logs -n kuma-system deployment/kuma-control-plane | grep -i error
```

2. Verify Global CP address is reachable:
```bash
kubectl exec -n kuma-system deployment/kuma-control-plane -- \
  curl -k https://kuma-global.example.com:5685
```

3. Check TLS certificates:
```bash
kubectl get secrets -n kuma-system | grep kds
```

### Cross-Zone Traffic Failing

1. Check Zone Ingress is running and has external IP:
```bash
kubectl get svc -n kuma-system -l app.kubernetes.io/name=kuma-ingress
```

2. Verify Zone Egress can reach Zone Ingress:
```bash
kubectl logs -n kuma-system deployment/kuma-egress | grep -i error
```

3. Check Dataplane status:
```bash
kubectl get dataplanes -n kuma-system -o wide
```

### Service Not Discoverable Cross-Zone

1. Verify service is registered:
```bash
# On Global CP cluster
kumactl get dataplanes --mesh default | grep service-name
```

2. Check service is in crossClusterServices list
3. Verify MeshTrafficPermission allows access

### Certificate Issues

1. Check certificate expiry:
```bash
kubectl get secrets -n kuma-system kuma-tls-cert -o jsonpath='{.data.tls\.crt}' | \
  base64 -d | openssl x509 -noout -dates
```

2. Force certificate rotation:
```bash
kubectl delete secret -n kuma-system kuma-tls-cert
kubectl rollout restart deployment/kuma-control-plane -n kuma-system
```

## Best Practices

1. **Start with Global CP**: Deploy and verify Global CP before adding zones
2. **One Zone at a Time**: Add zones incrementally, verify each one
3. **Test Cross-Zone**: Use test services to verify connectivity before production traffic
4. **Monitor KDS**: Set up alerts for KDS connection failures
5. **Document Network**: Keep network diagrams and firewall rules updated
6. **Regular Testing**: Periodically test zone failover scenarios
