"""Circuit breaker component - MeshCircuitBreaker."""

from typing import List, Optional

import pulumi_kubernetes as k8s
from pulumi import ComponentResource, ResourceOptions

from config import KumaConfig


class CircuitBreaker(ComponentResource):
    """Creates MeshCircuitBreaker policies for managed services."""

    def __init__(
        self,
        name: str,
        config: KumaConfig,
        k8s_provider: k8s.Provider,
        opts: Optional[ResourceOptions] = None,
    ):
        super().__init__("kuma:orchestration:CircuitBreaker", name, None, opts)

        self.circuit_breakers: List[k8s.apiextensions.CustomResource] = []

        # Create MeshCircuitBreaker for each managed service
        for service in config.managed_services:
            circuit_breaker = k8s.apiextensions.CustomResource(
                f"{name}-circuit-breaker-{service}",
                api_version="kuma.io/v1alpha1",
                kind="MeshCircuitBreaker",
                metadata=k8s.meta.v1.ObjectMetaArgs(
                    name=f"{service}-circuit-breaker",
                    namespace=config.kuma_namespace,
                    labels={
                        "kuma.io/mesh": config.mesh_name,
                        "kuma.io/origin": "zone",
                        "app": service,
                    },
                ),
                spec={
                    "targetRef": {
                        "kind": "MeshService",
                        "name": service,
                    },
                    "to": [
                        {
                            "targetRef": {
                                "kind": "MeshService",
                                "name": service,
                            },
                            "default": {
                                "connectionLimits": {
                                    "maxConnections": config.circuit_breaker_max_connections,
                                    "maxPendingRequests": config.circuit_breaker_max_pending,
                                    "maxRequests": config.circuit_breaker_max_requests,
                                    "maxRetries": config.circuit_breaker_max_retries,
                                },
                                "outlierDetection": {
                                    "disabled": False,
                                    "interval": f"{config.outlier_interval}s",
                                    "baseEjectionTime": f"{config.outlier_base_ejection_time}s",
                                    "maxEjectionPercent": config.outlier_max_ejection_percent,
                                    "splitExternalAndLocalErrors": True,
                                    "detectors": {
                                        "totalFailures": {
                                            "consecutive": config.outlier_consecutive_errors,
                                        },
                                        "gatewayFailures": {
                                            "consecutive": config.outlier_consecutive_errors,
                                        },
                                        "localOriginFailures": {
                                            "consecutive": config.outlier_consecutive_errors,
                                        },
                                    },
                                },
                            },
                        }
                    ],
                },
                opts=ResourceOptions(parent=self, provider=k8s_provider),
            )
            self.circuit_breakers.append(circuit_breaker)

        self.register_outputs(
            {
                "circuit_breaker_count": len(self.circuit_breakers),
                "max_connections": config.circuit_breaker_max_connections,
            }
        )
