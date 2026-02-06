"""Traffic routing component - MeshHTTPRoute and MeshTCPRoute."""

from typing import List, Optional

import pulumi_kubernetes as k8s
from pulumi import ComponentResource, ResourceOptions

from config import KumaConfig


class TrafficRouting(ComponentResource):
    """Creates MeshHTTPRoute and MeshTCPRoute policies for managed services."""

    def __init__(
        self,
        name: str,
        config: KumaConfig,
        k8s_provider: k8s.Provider,
        opts: Optional[ResourceOptions] = None,
    ):
        super().__init__("kuma:orchestration:TrafficRouting", name, None, opts)

        self.http_routes: List[k8s.apiextensions.CustomResource] = []
        self.tcp_routes: List[k8s.apiextensions.CustomResource] = []

        # Create MeshHTTPRoute for each managed service
        for service in config.managed_services:
            http_route = k8s.apiextensions.CustomResource(
                f"{name}-http-route-{service}",
                api_version="kuma.io/v2alpha1",
                kind="MeshHTTPRoute",
                metadata=k8s.meta.v1.ObjectMetaArgs(
                    name=f"{service}-http-route",
                    namespace=config.kuma_namespace,
                    labels={
                        "kuma.io/mesh": config.mesh_name,
                        "kuma.io/origin": "zone",
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
                            "rules": [
                                {
                                    "matches": [
                                        {
                                            "path": {
                                                "type": "PathPrefix",
                                                "value": "/",
                                            },
                                        }
                                    ],
                                    "default": {
                                        "backendRefs": [
                                            {
                                                "kind": "MeshService",
                                                "name": service,
                                                "weight": 100,
                                            }
                                        ],
                                    },
                                }
                            ],
                        }
                    ],
                },
                opts=ResourceOptions(parent=self, provider=k8s_provider),
            )
            self.http_routes.append(http_route)

            # Create MeshTCPRoute for each managed service
            tcp_route = k8s.apiextensions.CustomResource(
                f"{name}-tcp-route-{service}",
                api_version="kuma.io/v2alpha1",
                kind="MeshTCPRoute",
                metadata=k8s.meta.v1.ObjectMetaArgs(
                    name=f"{service}-tcp-route",
                    namespace=config.kuma_namespace,
                    labels={
                        "kuma.io/mesh": config.mesh_name,
                        "kuma.io/origin": "zone",
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
                            "rules": [
                                {
                                    "default": {
                                        "backendRefs": [
                                            {
                                                "kind": "MeshService",
                                                "name": service,
                                                "weight": 100,
                                            }
                                        ],
                                    },
                                }
                            ],
                        }
                    ],
                },
                opts=ResourceOptions(parent=self, provider=k8s_provider),
            )
            self.tcp_routes.append(tcp_route)

        self.register_outputs(
            {
                "http_route_count": len(self.http_routes),
                "tcp_route_count": len(self.tcp_routes),
            }
        )
