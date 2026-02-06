# Nginx Kuma Service Mesh Demo

This example demonstrates deploying an Nginx application with Kuma service mesh integration, including:

- Automatic sidecar injection
- mTLS encryption between services
- Traffic permissions
- Rate limiting
- Circuit breaker
- Observability (metrics, tracing, logging)

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                     nginx-demo namespace                         │
│                                                                  │
│  ┌──────────────────────┐        ┌──────────────────────┐       │
│  │    curl-client       │        │      nginx           │       │
│  │  ┌───────────────┐   │        │  ┌───────────────┐   │       │
│  │  │ curl container│   │        │  │nginx container│   │       │
│  │  └───────┬───────┘   │        │  └───────┬───────┘   │       │
│  │          │           │        │          │           │       │
│  │  ┌───────▼───────┐   │  mTLS  │  ┌───────▼───────┐   │       │
│  │  │ kuma-sidecar  │◄──┼────────┼──► kuma-sidecar  │   │       │
│  │  │   (envoy)     │   │        │  │   (envoy)     │   │       │
│  │  └───────────────┘   │        │  └───────────────┘   │       │
│  └──────────────────────┘        └──────────────────────┘       │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                       Kuma Control Plane                         │
│                                                                  │
│  • MeshTrafficPermission: Allow curl → nginx                    │
│  • MeshRateLimit: 100 RPS                                       │
│  • MeshCircuitBreaker: Max 512 connections                      │
│  • MeshTimeout: 15s request timeout                             │
│  • MeshRetry: 3 attempts on 5xx                                 │
│  • MeshAccessLog: JSON to stdout                                │
│  • MeshTrace: Jaeger integration                                │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

## Prerequisites

- EKS cluster with Kuma installed (via `infra/` project)
- Kuma policies deployed (via `kuma-orchestration/` project)
- kubectl configured to access the cluster

## Quick Start

### 1. Deploy the Application

```bash
# Deploy all resources
kubectl apply -f examples/nginx-kuma-demo/

# Or deploy individually
kubectl apply -f examples/nginx-kuma-demo/01-namespace.yaml
kubectl apply -f examples/nginx-kuma-demo/02-nginx.yaml
kubectl apply -f examples/nginx-kuma-demo/03-client.yaml
kubectl apply -f examples/nginx-kuma-demo/04-policies.yaml
```

### 2. Verify Deployment

```bash
# Check pods (should have 2/2 containers - app + sidecar)
kubectl get pods -n nginx-demo

# Expected output:
# NAME                           READY   STATUS    RESTARTS   AGE
# curl-client-xxxxx              2/2     Running   0          1m
# nginx-xxxxx                    2/2     Running   0          1m

# Check services
kubectl get svc -n nginx-demo
```

### 3. Test Service Communication

```bash
# Exec into curl client
kubectl exec -it deployment/curl-client -n nginx-demo -c curl -- sh

# Test nginx service (mTLS encrypted automatically)
curl http://nginx.nginx-demo.svc.cluster.local

# Expected output: Nginx welcome page HTML

# Test multiple requests (rate limiting test)
for i in $(seq 1 150); do
  curl -s -o /dev/null -w "%{http_code}\n" http://nginx.nginx-demo.svc.cluster.local
done

# After ~100 requests, you should see 429 (rate limited)
```

### 4. Verify mTLS

```bash
# Check that traffic is encrypted
kubectl get dataplanes -n nginx-demo -o yaml | grep -A5 "mtls"

# Check mesh configuration
kubectl get mesh default -o yaml
```

### 5. View Metrics

```bash
# Port-forward to Prometheus
kubectl port-forward -n observability svc/prometheus-server 9090:80

# Open http://localhost:9090
# Query: envoy_cluster_upstream_rq_total{kuma_io_service="nginx_nginx-demo_svc_80"}
```

### 6. View Traces

```bash
# Port-forward to Jaeger
kubectl port-forward -n observability svc/jaeger-query 16686:16686

# Open http://localhost:16686
# Select service: nginx_nginx-demo_svc_80
```

### 7. View Access Logs

```bash
# View sidecar logs (access logs in JSON format)
kubectl logs deployment/nginx -n nginx-demo -c kuma-sidecar | jq .
```

## Files

| File | Description |
|------|-------------|
| `01-namespace.yaml` | Namespace with sidecar injection enabled |
| `02-nginx.yaml` | Nginx deployment and service |
| `03-client.yaml` | Curl client for testing |
| `04-policies.yaml` | Kuma mesh policies for nginx |

## Kuma Policies Applied

### MeshTrafficPermission

Allows traffic from `curl-client` to `nginx`:

```yaml
spec:
  targetRef:
    kind: MeshService
    name: nginx_nginx-demo_svc_80
  from:
    - targetRef:
        kind: MeshSubset
        tags:
          app: curl-client
      default:
        action: Allow
```

### MeshRateLimit

Limits nginx to 100 requests per second:

```yaml
spec:
  targetRef:
    kind: MeshService
    name: nginx_nginx-demo_svc_80
  from:
    - targetRef:
        kind: Mesh
      default:
        local:
          http:
            requestRate:
              num: 100
              interval: 1s
```

### MeshCircuitBreaker

Protects nginx from overload:

```yaml
spec:
  targetRef:
    kind: MeshService
    name: nginx_nginx-demo_svc_80
  to:
    - targetRef:
        kind: MeshService
        name: nginx_nginx-demo_svc_80
      default:
        connectionLimits:
          maxConnections: 512
          maxPendingRequests: 512
```

### MeshTimeout

Sets request timeouts:

```yaml
spec:
  targetRef:
    kind: MeshService
    name: nginx_nginx-demo_svc_80
  to:
    - default:
        http:
          requestTimeout: 15s
          idleTimeout: 60s
```

### MeshRetry

Retries failed requests:

```yaml
spec:
  targetRef:
    kind: MeshService
    name: nginx_nginx-demo_svc_80
  to:
    - default:
        http:
          numRetries: 3
          retryOn:
            - 5xx
            - reset
            - connect-failure
```

## Cleanup

```bash
kubectl delete -f examples/nginx-kuma-demo/
```

## Troubleshooting

### Pods stuck at 1/2 containers

Sidecar injection may have failed. Check:

```bash
# Verify namespace has injection label
kubectl get ns nginx-demo -o yaml | grep sidecar-injection

# Check Kuma control plane logs
kubectl logs -n kuma-system deployment/kuma-control-plane
```

### Connection refused errors

Traffic permission may be blocking. Check:

```bash
# List traffic permissions
kubectl get meshtrafficpermission -n kuma-system

# Check specific permission
kubectl get meshtrafficpermission nginx-traffic-permission -n kuma-system -o yaml
```

### Rate limit not working

Verify the rate limit policy is applied:

```bash
kubectl get meshratelimit -n kuma-system
kubectl describe meshratelimit nginx-rate-limit -n kuma-system
```

### No traces appearing

Check Jaeger collector is running and MeshTrace policy is applied:

```bash
kubectl get pods -n observability | grep jaeger
kubectl get meshtrace -n kuma-system
```
