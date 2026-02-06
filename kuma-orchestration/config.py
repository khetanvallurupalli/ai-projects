"""Typed configuration loader for Kuma orchestration with multi-cluster support."""

from dataclasses import dataclass, field
from typing import Dict, List, Optional
from enum import Enum

import pulumi


class ClusterType(Enum):
    """Supported Kubernetes cluster types."""
    EKS = "eks"
    AKS = "aks"
    AKS_LOCAL = "aks-local"  # Azure Arc-enabled AKS on-premises
    GKE = "gke"
    KIND = "kind"  # For local development
    K3S = "k3s"
    OPENSHIFT = "openshift"
    RANCHER = "rancher"


class KumaMode(Enum):
    """Kuma deployment modes."""
    STANDALONE = "standalone"  # Single cluster, no federation
    GLOBAL = "global"  # Global control plane for multi-zone
    ZONE = "zone"  # Zone control plane connected to global


@dataclass
class ClusterConfig:
    """Configuration for a single Kubernetes cluster."""
    name: str
    type: ClusterType
    zone_name: str
    region: str
    # Stack reference to get kubeconfig (for Pulumi-managed clusters)
    infra_stack_name: Optional[str] = None
    # Direct kubeconfig (for external clusters)
    kubeconfig_secret_name: Optional[str] = None
    # Cluster-specific settings
    is_global_cp_cluster: bool = False
    zone_ingress_enabled: bool = True
    zone_egress_enabled: bool = True
    # Network settings for cross-cluster communication
    pod_cidr: Optional[str] = None
    service_cidr: Optional[str] = None
    # Cloud-specific settings
    cloud_provider_settings: Dict[str, str] = field(default_factory=dict)


@dataclass
class CrossClusterConfig:
    """Configuration for cross-cluster service mesh."""
    enabled: bool = True
    # mTLS settings for cross-cluster communication
    mtls_mode: str = "strict"  # strict, permissive
    ca_backend: str = "builtin"  # builtin, vault, cert-manager
    # Certificate settings
    cert_validity_days: int = 365
    cert_rotation_threshold_percent: int = 80
    # Cross-cluster service discovery
    universal_service_discovery: bool = True
    # External service passthrough
    passthrough_mode: str = "none"  # none, matched, all
    # Locality-aware load balancing
    locality_aware_lb_enabled: bool = True
    locality_priority_weight: int = 100
    # Cross-zone traffic settings
    cross_zone_traffic_enabled: bool = True
    cross_zone_traffic_default_action: str = "Allow"  # Allow, Deny


@dataclass
class GlobalCPConfig:
    """Configuration for Global Control Plane."""
    enabled: bool = True
    # Dedicated cluster or co-located
    dedicated_cluster: bool = False
    dedicated_cluster_name: Optional[str] = None
    # HA settings
    replicas: int = 3
    # KDS (Kuma Discovery Service) settings
    kds_port: int = 5685
    kds_tls_enabled: bool = True
    # Global Zone Sync Service
    zone_sync_service_type: str = "LoadBalancer"  # LoadBalancer, NodePort, ClusterIP
    # External address (if using external LB or DNS)
    external_address: Optional[str] = None
    external_port: int = 5685


@dataclass
class KumaConfig:
    """Configuration for Kuma service mesh deployment."""

    # ===== Multi-Cluster Settings =====
    mode: KumaMode
    clusters: List[ClusterConfig]
    global_cp: GlobalCPConfig
    cross_cluster: CrossClusterConfig

    # ===== Current Cluster Context =====
    # Which cluster this stack is deploying to
    current_cluster_name: str

    # ===== Kuma Core Settings =====
    kuma_version: str
    kuma_namespace: str
    mesh_name: str
    mtls_enabled: bool
    mtls_backend: str  # "builtin" or "provided"

    # ===== Timeout Settings (seconds) =====
    http_request_timeout: int
    http_idle_timeout: int
    tcp_idle_timeout: int

    # ===== Retry Settings =====
    retry_attempts: int
    retry_per_try_timeout: int
    retry_backoff_base: int
    retry_backoff_max: int

    # ===== Rate Limit Settings =====
    rate_limit_rps: int
    rate_limit_burst: int

    # ===== Circuit Breaker Settings =====
    circuit_breaker_max_connections: int
    circuit_breaker_max_pending: int
    circuit_breaker_max_requests: int
    circuit_breaker_max_retries: int
    outlier_consecutive_errors: int
    outlier_interval: int
    outlier_base_ejection_time: int
    outlier_max_ejection_percent: int

    # ===== Observability Settings =====
    prometheus_port: int
    tracing_backend: str  # "jaeger" or "datadog"
    trace_sample_rate: float
    logging_format: str  # "json" or "text"
    datadog_agent_address: Optional[str] = None

    # ===== Fault Injection (dev only) =====
    fault_injection_enabled: bool = False
    fault_injection_abort_percent: float = 0.0
    fault_injection_delay_percent: float = 0.0
    fault_injection_delay_ms: int = 0

    # ===== Traffic Permissions =====
    traffic_permission_default_action: str = "Deny"

    # ===== Managed Services =====
    managed_services: List[str] = field(default_factory=list)

    # ===== Cross-Cluster Services =====
    # Services that should be accessible across clusters
    cross_cluster_services: List[str] = field(default_factory=list)

    # ===== Environment =====
    environment: str = "dev"

    def get_current_cluster(self) -> ClusterConfig:
        """Get the configuration for the current cluster."""
        for cluster in self.clusters:
            if cluster.name == self.current_cluster_name:
                return cluster
        raise ValueError(f"Cluster '{self.current_cluster_name}' not found in configuration")

    def get_global_cp_cluster(self) -> Optional[ClusterConfig]:
        """Get the cluster hosting the global control plane."""
        for cluster in self.clusters:
            if cluster.is_global_cp_cluster:
                return cluster
        return None

    def get_zone_clusters(self) -> List[ClusterConfig]:
        """Get all zone clusters (non-global CP clusters)."""
        return [c for c in self.clusters if not c.is_global_cp_cluster]

    def is_multi_cluster(self) -> bool:
        """Check if this is a multi-cluster deployment."""
        return len(self.clusters) > 1 and self.cross_cluster.enabled


def _parse_cluster_config(cluster_dict: Dict) -> ClusterConfig:
    """Parse a cluster configuration dictionary."""
    return ClusterConfig(
        name=cluster_dict.get("name", ""),
        type=ClusterType(cluster_dict.get("type", "eks")),
        zone_name=cluster_dict.get("zoneName", ""),
        region=cluster_dict.get("region", ""),
        infra_stack_name=cluster_dict.get("infraStackName"),
        kubeconfig_secret_name=cluster_dict.get("kubeconfigSecretName"),
        is_global_cp_cluster=cluster_dict.get("isGlobalCpCluster", False),
        zone_ingress_enabled=cluster_dict.get("zoneIngressEnabled", True),
        zone_egress_enabled=cluster_dict.get("zoneEgressEnabled", True),
        pod_cidr=cluster_dict.get("podCidr"),
        service_cidr=cluster_dict.get("serviceCidr"),
        cloud_provider_settings=cluster_dict.get("cloudProviderSettings", {}),
    )


def load_config() -> KumaConfig:
    """Load configuration from Pulumi config."""
    config = pulumi.Config()
    kuma_config = pulumi.Config("kuma")
    cluster_config = pulumi.Config("cluster")
    cross_cluster_cfg = pulumi.Config("crossCluster")

    # Helper functions
    def get_int(cfg: pulumi.Config, key: str, default: int) -> int:
        return cfg.get_int(key) or default

    def get_float(cfg: pulumi.Config, key: str, default: float) -> float:
        val = cfg.get(key)
        return float(val) if val else default

    def get_str(cfg: pulumi.Config, key: str, default: str) -> str:
        return cfg.get(key) or default

    def get_bool(cfg: pulumi.Config, key: str, default: bool) -> bool:
        val = cfg.get_bool(key)
        return val if val is not None else default

    environment = config.get("environment") or "dev"

    # Parse clusters configuration
    clusters_data = cluster_config.get_object("clusters") or []
    clusters = [_parse_cluster_config(c) for c in clusters_data]

    # If no clusters defined, create a default single-cluster config
    if not clusters:
        default_infra_stack = config.get("infraStackName")
        if default_infra_stack:
            clusters = [ClusterConfig(
                name=f"{environment}-cluster",
                type=ClusterType.EKS,
                zone_name=f"{environment}-zone",
                region="us-west-2",
                infra_stack_name=default_infra_stack,
                is_global_cp_cluster=True,
            )]

    # Parse global CP configuration
    global_cp_data = kuma_config.get_object("globalCp") or {}
    global_cp = GlobalCPConfig(
        enabled=global_cp_data.get("enabled", True),
        dedicated_cluster=global_cp_data.get("dedicatedCluster", False),
        dedicated_cluster_name=global_cp_data.get("dedicatedClusterName"),
        replicas=global_cp_data.get("replicas", 3),
        kds_port=global_cp_data.get("kdsPort", 5685),
        kds_tls_enabled=global_cp_data.get("kdsTlsEnabled", True),
        zone_sync_service_type=global_cp_data.get("zoneSyncServiceType", "LoadBalancer"),
        external_address=global_cp_data.get("externalAddress"),
        external_port=global_cp_data.get("externalPort", 5685),
    )

    # Parse cross-cluster configuration
    cross_cluster = CrossClusterConfig(
        enabled=get_bool(cross_cluster_cfg, "enabled", len(clusters) > 1),
        mtls_mode=get_str(cross_cluster_cfg, "mtlsMode", "strict"),
        ca_backend=get_str(cross_cluster_cfg, "caBackend", "builtin"),
        cert_validity_days=get_int(cross_cluster_cfg, "certValidityDays", 365),
        cert_rotation_threshold_percent=get_int(cross_cluster_cfg, "certRotationThreshold", 80),
        universal_service_discovery=get_bool(cross_cluster_cfg, "universalServiceDiscovery", True),
        passthrough_mode=get_str(cross_cluster_cfg, "passthroughMode", "none"),
        locality_aware_lb_enabled=get_bool(cross_cluster_cfg, "localityAwareLb", True),
        locality_priority_weight=get_int(cross_cluster_cfg, "localityPriorityWeight", 100),
        cross_zone_traffic_enabled=get_bool(cross_cluster_cfg, "crossZoneTrafficEnabled", True),
        cross_zone_traffic_default_action=get_str(cross_cluster_cfg, "crossZoneTrafficDefault", "Allow"),
    )

    # Determine Kuma mode
    mode_str = get_str(kuma_config, "mode", "standalone")
    mode = KumaMode(mode_str) if mode_str in [m.value for m in KumaMode] else KumaMode.STANDALONE

    # Get current cluster name
    current_cluster = get_str(cluster_config, "currentCluster",
                               clusters[0].name if clusters else "default")

    return KumaConfig(
        # Multi-cluster settings
        mode=mode,
        clusters=clusters,
        global_cp=global_cp,
        cross_cluster=cross_cluster,
        current_cluster_name=current_cluster,
        # Kuma core settings
        kuma_version=get_str(kuma_config, "version", "2.6.0"),
        kuma_namespace=get_str(kuma_config, "namespace", "kuma-system"),
        mesh_name=get_str(kuma_config, "meshName", "default"),
        mtls_enabled=get_bool(kuma_config, "mtlsEnabled", True),
        mtls_backend=get_str(kuma_config, "mtlsBackend", "builtin"),
        # Timeout settings
        http_request_timeout=get_int(kuma_config, "httpRequestTimeout", 15),
        http_idle_timeout=get_int(kuma_config, "httpIdleTimeout", 60),
        tcp_idle_timeout=get_int(kuma_config, "tcpIdleTimeout", 3600),
        # Retry settings
        retry_attempts=get_int(kuma_config, "retryAttempts", 3),
        retry_per_try_timeout=get_int(kuma_config, "retryPerTryTimeout", 5),
        retry_backoff_base=get_int(kuma_config, "retryBackoffBase", 25),
        retry_backoff_max=get_int(kuma_config, "retryBackoffMax", 250),
        # Rate limit settings
        rate_limit_rps=get_int(kuma_config, "rateLimitRps", 100),
        rate_limit_burst=get_int(kuma_config, "rateLimitBurst", 200),
        # Circuit breaker settings
        circuit_breaker_max_connections=get_int(kuma_config, "circuitBreakerMaxConnections", 512),
        circuit_breaker_max_pending=get_int(kuma_config, "circuitBreakerMaxPending", 512),
        circuit_breaker_max_requests=get_int(kuma_config, "circuitBreakerMaxRequests", 512),
        circuit_breaker_max_retries=get_int(kuma_config, "circuitBreakerMaxRetries", 3),
        outlier_consecutive_errors=get_int(kuma_config, "outlierConsecutiveErrors", 5),
        outlier_interval=get_int(kuma_config, "outlierInterval", 10),
        outlier_base_ejection_time=get_int(kuma_config, "outlierBaseEjectionTime", 30),
        outlier_max_ejection_percent=get_int(kuma_config, "outlierMaxEjectionPercent", 50),
        # Observability settings
        prometheus_port=get_int(kuma_config, "prometheusPort", 5670),
        tracing_backend=get_str(kuma_config, "tracingBackend", "jaeger"),
        trace_sample_rate=get_float(kuma_config, "traceSampleRate", 0.5),
        logging_format=get_str(kuma_config, "loggingFormat", "json"),
        datadog_agent_address=kuma_config.get("datadogAgentAddress"),
        # Fault injection
        fault_injection_enabled=get_bool(kuma_config, "faultInjectionEnabled", environment == "dev"),
        fault_injection_abort_percent=get_float(kuma_config, "faultInjectionAbortPercent", 0.1),
        fault_injection_delay_percent=get_float(kuma_config, "faultInjectionDelayPercent", 0.1),
        fault_injection_delay_ms=get_int(kuma_config, "faultInjectionDelayMs", 100),
        # Traffic permissions
        traffic_permission_default_action=get_str(kuma_config, "trafficPermissionDefault",
                                                   "Allow" if environment == "dev" else "Deny"),
        # Managed services
        managed_services=kuma_config.get_object("managedServices") or [],
        # Cross-cluster services
        cross_cluster_services=kuma_config.get_object("crossClusterServices") or [],
        # Environment
        environment=environment,
    )
