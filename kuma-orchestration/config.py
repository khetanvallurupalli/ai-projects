"""Typed configuration loader for Kuma orchestration."""

from dataclasses import dataclass, field
from typing import List, Optional

import pulumi


@dataclass
class KumaConfig:
    """Configuration for Kuma service mesh deployment."""

    # Stack reference
    infra_stack_name: str

    # Kuma settings
    kuma_version: str
    kuma_mode: str  # "zone" or "global"
    kuma_namespace: str
    kuma_global_address: Optional[str]  # Required for zone mode
    kuma_zone_name: str

    # Mesh settings
    mesh_name: str
    mtls_enabled: bool
    mtls_backend: str  # "builtin" or "provided"

    # Timeout settings (seconds)
    http_request_timeout: int
    http_idle_timeout: int
    tcp_idle_timeout: int

    # Retry settings
    retry_attempts: int
    retry_per_try_timeout: int
    retry_backoff_base: int
    retry_backoff_max: int

    # Rate limit settings
    rate_limit_rps: int
    rate_limit_burst: int

    # Circuit breaker settings
    circuit_breaker_max_connections: int
    circuit_breaker_max_pending: int
    circuit_breaker_max_requests: int
    circuit_breaker_max_retries: int
    outlier_consecutive_errors: int
    outlier_interval: int
    outlier_base_ejection_time: int
    outlier_max_ejection_percent: int

    # Observability settings
    prometheus_port: int
    tracing_backend: str  # "jaeger" or "datadog"
    trace_sample_rate: float
    logging_format: str  # "json" or "text"
    datadog_agent_address: Optional[str]

    # Fault injection (dev only)
    fault_injection_enabled: bool
    fault_injection_abort_percent: float
    fault_injection_delay_percent: float
    fault_injection_delay_ms: int

    # Traffic permissions
    traffic_permission_default_action: str  # "Allow" or "Deny"

    # Managed services
    managed_services: List[str] = field(default_factory=list)

    # Environment
    environment: str = "dev"


def load_config() -> KumaConfig:
    """Load configuration from Pulumi config."""
    config = pulumi.Config()
    kuma_config = pulumi.Config("kuma")

    # Helper to get nested config with defaults
    def get_int(key: str, default: int) -> int:
        return kuma_config.get_int(key) or default

    def get_float(key: str, default: float) -> float:
        val = kuma_config.get(key)
        return float(val) if val else default

    def get_str(key: str, default: str) -> str:
        return kuma_config.get(key) or default

    def get_bool(key: str, default: bool) -> bool:
        val = kuma_config.get_bool(key)
        return val if val is not None else default

    environment = config.get("environment") or "dev"

    return KumaConfig(
        # Stack reference
        infra_stack_name=config.require("infraStackName"),
        # Kuma settings
        kuma_version=get_str("version", "2.6.0"),
        kuma_mode=get_str("mode", "zone"),
        kuma_namespace=get_str("namespace", "kuma-system"),
        kuma_global_address=kuma_config.get("globalAddress"),
        kuma_zone_name=get_str("zoneName", f"{environment}-zone"),
        # Mesh settings
        mesh_name=get_str("meshName", "default"),
        mtls_enabled=get_bool("mtlsEnabled", True),
        mtls_backend=get_str("mtlsBackend", "builtin"),
        # Timeout settings
        http_request_timeout=get_int("httpRequestTimeout", 15),
        http_idle_timeout=get_int("httpIdleTimeout", 60),
        tcp_idle_timeout=get_int("tcpIdleTimeout", 3600),
        # Retry settings
        retry_attempts=get_int("retryAttempts", 3),
        retry_per_try_timeout=get_int("retryPerTryTimeout", 5),
        retry_backoff_base=get_int("retryBackoffBase", 25),
        retry_backoff_max=get_int("retryBackoffMax", 250),
        # Rate limit settings
        rate_limit_rps=get_int("rateLimitRps", 100),
        rate_limit_burst=get_int("rateLimitBurst", 200),
        # Circuit breaker settings
        circuit_breaker_max_connections=get_int("circuitBreakerMaxConnections", 512),
        circuit_breaker_max_pending=get_int("circuitBreakerMaxPending", 512),
        circuit_breaker_max_requests=get_int("circuitBreakerMaxRequests", 512),
        circuit_breaker_max_retries=get_int("circuitBreakerMaxRetries", 3),
        outlier_consecutive_errors=get_int("outlierConsecutiveErrors", 5),
        outlier_interval=get_int("outlierInterval", 10),
        outlier_base_ejection_time=get_int("outlierBaseEjectionTime", 30),
        outlier_max_ejection_percent=get_int("outlierMaxEjectionPercent", 50),
        # Observability settings
        prometheus_port=get_int("prometheusPort", 5670),
        tracing_backend=get_str("tracingBackend", "jaeger"),
        trace_sample_rate=get_float("traceSampleRate", 0.5),
        logging_format=get_str("loggingFormat", "json"),
        datadog_agent_address=kuma_config.get("datadogAgentAddress"),
        # Fault injection
        fault_injection_enabled=get_bool("faultInjectionEnabled", True),
        fault_injection_abort_percent=get_float("faultInjectionAbortPercent", 0.1),
        fault_injection_delay_percent=get_float("faultInjectionDelayPercent", 0.1),
        fault_injection_delay_ms=get_int("faultInjectionDelayMs", 100),
        # Traffic permissions
        traffic_permission_default_action=get_str("trafficPermissionDefault", "Allow"),
        # Managed services
        managed_services=kuma_config.get_object("managedServices") or [],
        # Environment
        environment=environment,
    )
