"""Kuma orchestration - main entrypoint with multi-cluster support."""

import pulumi

from config import load_config, KumaMode
from components import (
    ClusterReference,
    MultiClusterManager,
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
    CrossClusterPolicies,
    CrossClusterMTLS,
    create_cluster_provider,
)

# Load configuration
config = load_config()

# Determine deployment mode
is_multi_cluster = config.is_multi_cluster()
current_cluster = config.get_current_cluster()

# ============================================================================
# STEP 1: Set up cluster provider(s)
# ============================================================================

if is_multi_cluster:
    # Multi-cluster mode: create providers for all clusters
    cluster_manager = MultiClusterManager("cluster-manager", config)
    current_provider = cluster_manager.get_current_provider()
    k8s_provider = current_provider.k8s_provider
    cluster_name = current_provider.cluster_name
else:
    # Single cluster mode: use ClusterReference for backward compatibility
    if current_cluster.infra_stack_name:
        cluster_ref = ClusterReference("cluster-ref", config)
        k8s_provider = cluster_ref.k8s_provider
        cluster_name = cluster_ref.cluster_name
    else:
        # Use direct cluster provider
        provider = create_cluster_provider("cluster", current_cluster)
        k8s_provider = provider.k8s_provider
        cluster_name = provider.cluster_name

# ============================================================================
# STEP 2: Deploy Kuma Control Plane based on mode
# ============================================================================

kuma_cp = None
global_address = None

if config.mode == KumaMode.GLOBAL or (config.mode == KumaMode.STANDALONE and current_cluster.is_global_cp_cluster):
    # Deploy Global Control Plane
    kuma_cp = KumaGlobalControlPlane(
        "kuma-global-cp",
        config,
        k8s_provider,
    )
    global_address = kuma_cp.global_address

elif config.mode == KumaMode.ZONE:
    # Deploy Zone Control Plane
    # Get global address from config or previous deployment
    if config.global_cp.external_address:
        global_address = pulumi.Output.from_input(
            f"grpcs://{config.global_cp.external_address}:{config.global_cp.external_port}"
        )

    kuma_cp = KumaZoneControlPlane(
        "kuma-zone-cp",
        config,
        current_cluster,
        k8s_provider,
        global_address=global_address,
    )

else:
    # Standalone mode - deploy as zone CP without global connection
    kuma_cp = KumaZoneControlPlane(
        "kuma-zone-cp",
        config,
        current_cluster,
        k8s_provider,
    )

# ============================================================================
# STEP 3: Deploy Observability Stack
# ============================================================================

observability_stack = ObservabilityStack(
    "observability-stack",
    config,
    k8s_provider,
    opts=pulumi.ResourceOptions(depends_on=[kuma_cp]),
)

# ============================================================================
# STEP 4: Create Zone Resources
# ============================================================================

zone_resources = ZoneResources(
    "zone-resources",
    config,
    k8s_provider,
    cluster_config=current_cluster,
    opts=pulumi.ResourceOptions(depends_on=[kuma_cp]),
)

# ============================================================================
# STEP 5: Deploy Cross-Cluster Policies (if multi-cluster)
# ============================================================================

cross_cluster_policies = None
cross_cluster_mtls = None

if is_multi_cluster and config.cross_cluster.enabled:
    cross_cluster_mtls = CrossClusterMTLS(
        "cross-cluster-mtls",
        config,
        k8s_provider,
        opts=pulumi.ResourceOptions(depends_on=[zone_resources]),
    )

    cross_cluster_policies = CrossClusterPolicies(
        "cross-cluster-policies",
        config,
        k8s_provider,
        opts=pulumi.ResourceOptions(depends_on=[cross_cluster_mtls]),
    )

# ============================================================================
# STEP 6: Create Traffic and Resilience Policies
# ============================================================================

# These run in parallel after zone resources
policy_depends = [zone_resources]
if cross_cluster_policies:
    policy_depends.append(cross_cluster_policies)

traffic_routing = TrafficRouting(
    "traffic-routing",
    config,
    k8s_provider,
    opts=pulumi.ResourceOptions(depends_on=policy_depends),
)

traffic_permissions = TrafficPermissions(
    "traffic-permissions",
    config,
    k8s_provider,
    opts=pulumi.ResourceOptions(depends_on=policy_depends),
)

rate_limiting = RateLimiting(
    "rate-limiting",
    config,
    k8s_provider,
    opts=pulumi.ResourceOptions(depends_on=policy_depends),
)

circuit_breaker = CircuitBreaker(
    "circuit-breaker",
    config,
    k8s_provider,
    opts=pulumi.ResourceOptions(depends_on=policy_depends),
)

resilience = Resilience(
    "resilience",
    config,
    k8s_provider,
    opts=pulumi.ResourceOptions(depends_on=policy_depends),
)

# ============================================================================
# STEP 7: Fault Injection (dev only)
# ============================================================================

fault_injection = FaultInjection(
    "fault-injection",
    config,
    k8s_provider,
    opts=pulumi.ResourceOptions(depends_on=policy_depends),
)

# ============================================================================
# STEP 8: Observability Policies
# ============================================================================

observability_policies = ObservabilityPolicies(
    "observability-policies",
    config,
    k8s_provider,
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

# ============================================================================
# Exports
# ============================================================================

pulumi.export("cluster_name", cluster_name)
pulumi.export("cluster_type", current_cluster.type.value)
pulumi.export("kuma_namespace", config.kuma_namespace)
pulumi.export("mesh_name", config.mesh_name)
pulumi.export("zone_name", current_cluster.zone_name)
pulumi.export("observability_namespace", "observability")
pulumi.export("environment", config.environment)
pulumi.export("managed_services", config.managed_services)
pulumi.export("kuma_mode", config.mode.value)

# Multi-cluster specific exports
pulumi.export("is_multi_cluster", is_multi_cluster)
pulumi.export("cross_cluster_enabled", config.cross_cluster.enabled if is_multi_cluster else False)
pulumi.export("cross_cluster_namespaces", [
    {"namespace": ns.namespace, "services": ns.services, "all_services": ns.all_services}
    for ns in config.cross_cluster_namespaces
])

if global_address:
    pulumi.export("global_cp_address", global_address)
