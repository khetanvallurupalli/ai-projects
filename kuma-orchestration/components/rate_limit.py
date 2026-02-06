"""Rate limiting component - MeshRateLimit."""

from typing import List, Optional

import pulumi_kubernetes as k8s
from pulumi import ComponentResource, ResourceOptions

from config import KumaConfig


class RateLimiting(ComponentResource):
    """Creates MeshRateLimit policies for managed services."""

    def __init__(
        self,
        name: str,
        config: KumaConfig,
        k8s_provider: k8s.Provider,
        opts: Optional[ResourceOptions] = None,
    ):
        super().__init__("kuma:orchestration:RateLimiting", name, None, opts)

        self.rate_limits: List[k8s.apiextensions.CustomResource] = []

        # Create MeshRateLimit for each managed service
        for service in config.managed_services:
            rate_limit = k8s.apiextensions.CustomResource(
                f"{name}-rate-limit-{service}",
                api_version="kuma.io/v1alpha1",
                kind="MeshRateLimit",
                metadata=k8s.meta.v1.ObjectMetaArgs(
                    name=f"{service}-rate-limit",
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
                    "from": [
                        {
                            "targetRef": {
                                "kind": "Mesh",
                            },
                            "default": {
                                "local": {
                                    "http": {
                                        "requestRate": {
                                            "num": config.rate_limit_rps,
                                            "interval": "1s",
                                        },
                                        "onRateLimit": {
                                            "status": 429,
                                            "headers": {
                                                "add": [
                                                    {
                                                        "name": "x-rate-limited",
                                                        "value": "true",
                                                    }
                                                ],
                                            },
                                        },
                                    },
                                },
                            },
                        }
                    ],
                },
                opts=ResourceOptions(parent=self, provider=k8s_provider),
            )
            self.rate_limits.append(rate_limit)

        self.register_outputs(
            {
                "rate_limit_count": len(self.rate_limits),
                "rps_per_service": config.rate_limit_rps,
            }
        )
