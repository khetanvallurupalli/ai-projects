"""Resilience component - MeshTimeout and MeshRetry."""

from typing import List, Optional

import pulumi_kubernetes as k8s
from pulumi import ComponentResource, ResourceOptions

from config import KumaConfig


class Resilience(ComponentResource):
    """Creates MeshTimeout and MeshRetry policies for managed services."""

    def __init__(
        self,
        name: str,
        config: KumaConfig,
        k8s_provider: k8s.Provider,
        opts: Optional[ResourceOptions] = None,
    ):
        super().__init__("kuma:orchestration:Resilience", name, None, opts)

        self.timeouts: List[k8s.apiextensions.CustomResource] = []
        self.retries: List[k8s.apiextensions.CustomResource] = []

        # Create MeshTimeout for each managed service
        for service in config.managed_services:
            timeout = k8s.apiextensions.CustomResource(
                f"{name}-timeout-{service}",
                api_version="kuma.io/v2alpha1",
                kind="MeshTimeout",
                metadata=k8s.meta.v1.ObjectMetaArgs(
                    name=f"{service}-timeout",
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
                                "http": {
                                    "requestTimeout": f"{config.http_request_timeout}s",
                                    "idleTimeout": f"{config.http_idle_timeout}s",
                                },
                                "tcp": {
                                    "idleTimeout": f"{config.tcp_idle_timeout}s",
                                },
                            },
                        }
                    ],
                },
                opts=ResourceOptions(parent=self, provider=k8s_provider),
            )
            self.timeouts.append(timeout)

            # Create MeshRetry for each managed service
            retry = k8s.apiextensions.CustomResource(
                f"{name}-retry-{service}",
                api_version="kuma.io/v2alpha1",
                kind="MeshRetry",
                metadata=k8s.meta.v1.ObjectMetaArgs(
                    name=f"{service}-retry",
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
                                "http": {
                                    "numRetries": config.retry_attempts,
                                    "perTryTimeout": f"{config.retry_per_try_timeout}s",
                                    "backOff": {
                                        "baseInterval": f"{config.retry_backoff_base}ms",
                                        "maxInterval": f"{config.retry_backoff_max}ms",
                                    },
                                    "retryOn": [
                                        "5xx",
                                        "reset",
                                        "connect-failure",
                                        "retriable-4xx",
                                        "refused-stream",
                                        "gateway-error",
                                    ],
                                },
                                "tcp": {
                                    "maxConnectAttempt": config.retry_attempts,
                                },
                            },
                        }
                    ],
                },
                opts=ResourceOptions(parent=self, provider=k8s_provider),
            )
            self.retries.append(retry)

        self.register_outputs(
            {
                "timeout_count": len(self.timeouts),
                "retry_count": len(self.retries),
                "http_timeout": f"{config.http_request_timeout}s",
                "retry_attempts": config.retry_attempts,
            }
        )
