"""Kuma orchestration - main entrypoint."""

import pulumi

from config import load_config
from components import (
    ClusterReference,
    KumaGlobalControlPlane,
    KumaZoneControlPlane,
    ZoneResources,
    TrafficRouting,
    TrafficPermissions,
    RateLimiting,
    CircuitBreaker,
    Resilience,
    FaultInjection,
    ObservabilityPolicies,
    ObservabilityStack,
)

# Load configuration
config = load_config()

# Step 1: Get cluster reference from infra stack
cluster_ref = ClusterReference("cluster-ref", config)

# Step 2: Deploy Kuma control plane based on mode
# For multi-zone setup: deploy global CP first, then zone CPs
# For standalone: deploy zone CP only
if config.kuma_mode == "global":
    # Global control plane
    kuma_cp = KumaGlobalControlPlane(
        "kuma-global-cp",
        config,
        cluster_ref.k8s_provider,
        opts=pulumi.ResourceOptions(depends_on=[cluster_ref]),
    )
else:
    # Zone control plane (default)
    kuma_cp = KumaZoneControlPlane(
        "kuma-zone-cp",
        config,
        cluster_ref.k8s_provider,
        opts=pulumi.ResourceOptions(depends_on=[cluster_ref]),
    )

# Step 3: Deploy observability stack (Prometheus + Jaeger)
# Can run in parallel with zone resources
observability_stack = ObservabilityStack(
    "observability-stack",
    config,
    cluster_ref.k8s_provider,
    opts=pulumi.ResourceOptions(depends_on=[kuma_cp]),
)

# Step 4: Create zone resources for multi-zone communication
zone_resources = ZoneResources(
    "zone-resources",
    config,
    cluster_ref.k8s_provider,
    opts=pulumi.ResourceOptions(depends_on=[kuma_cp]),
)

# Step 5: Create traffic and resilience policies
# These can all run in parallel after zone resources

traffic_routing = TrafficRouting(
    "traffic-routing",
    config,
    cluster_ref.k8s_provider,
    opts=pulumi.ResourceOptions(depends_on=[zone_resources]),
)

traffic_permissions = TrafficPermissions(
    "traffic-permissions",
    config,
    cluster_ref.k8s_provider,
    opts=pulumi.ResourceOptions(depends_on=[zone_resources]),
)

rate_limiting = RateLimiting(
    "rate-limiting",
    config,
    cluster_ref.k8s_provider,
    opts=pulumi.ResourceOptions(depends_on=[zone_resources]),
)

circuit_breaker = CircuitBreaker(
    "circuit-breaker",
    config,
    cluster_ref.k8s_provider,
    opts=pulumi.ResourceOptions(depends_on=[zone_resources]),
)

resilience = Resilience(
    "resilience",
    config,
    cluster_ref.k8s_provider,
    opts=pulumi.ResourceOptions(depends_on=[zone_resources]),
)

# Step 6: Fault injection (dev only)
fault_injection = FaultInjection(
    "fault-injection",
    config,
    cluster_ref.k8s_provider,
    opts=pulumi.ResourceOptions(depends_on=[zone_resources]),
)

# Step 7: Observability policies (depends on observability stack)
observability_policies = ObservabilityPolicies(
    "observability-policies",
    config,
    cluster_ref.k8s_provider,
    opts=pulumi.ResourceOptions(
        depends_on=[
            observability_stack,
            traffic_routing,
            traffic_permissions,
            rate_limiting,
            circuit_breaker,
            resilience,
            fault_injection,
        ]
    ),
)

# Export outputs
pulumi.export("cluster_name", cluster_ref.cluster_name)
pulumi.export("kuma_namespace", config.kuma_namespace)
pulumi.export("mesh_name", config.mesh_name)
pulumi.export("zone_name", config.kuma_zone_name)
pulumi.export("observability_namespace", "observability")
pulumi.export("environment", config.environment)
pulumi.export("managed_services", config.managed_services)
