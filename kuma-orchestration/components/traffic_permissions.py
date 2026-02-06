"""Traffic permissions component - MeshTrafficPermission."""

from typing import List, Optional

import pulumi_kubernetes as k8s
from pulumi import ComponentResource, ResourceOptions

from config import KumaConfig


class TrafficPermissions(ComponentResource):
    """Creates MeshTrafficPermission policies for service-to-service communication."""

    def __init__(
        self,
        name: str,
        config: KumaConfig,
        k8s_provider: k8s.Provider,
        opts: Optional[ResourceOptions] = None,
    ):
        super().__init__("kuma:orchestration:TrafficPermissions", name, None, opts)

        self.permissions: List[k8s.apiextensions.CustomResource] = []

        # Create default MeshTrafficPermission (Allow in dev, Deny in prod)
        self.default_permission = k8s.apiextensions.CustomResource(
            f"{name}-default-permission",
            api_version="kuma.io/v1alpha1",
            kind="MeshTrafficPermission",
            metadata=k8s.meta.v1.ObjectMetaArgs(
                name="default-traffic-permission",
                namespace=config.kuma_namespace,
                labels={
                    "kuma.io/mesh": config.mesh_name,
                    "kuma.io/origin": "zone",
                },
            ),
            spec={
                "targetRef": {
                    "kind": "Mesh",
                },
                "from": [
                    {
                        "targetRef": {
                            "kind": "Mesh",
                        },
                        "default": {
                            "action": config.traffic_permission_default_action,
                        },
                    }
                ],
            },
            opts=ResourceOptions(parent=self, provider=k8s_provider),
        )
        self.permissions.append(self.default_permission)

        # In prod (Deny default), create explicit allow rules for managed services
        if config.traffic_permission_default_action == "Deny":
            for service in config.managed_services:
                # Allow traffic from mesh to this service
                service_permission = k8s.apiextensions.CustomResource(
                    f"{name}-permission-{service}",
                    api_version="kuma.io/v1alpha1",
                    kind="MeshTrafficPermission",
                    metadata=k8s.meta.v1.ObjectMetaArgs(
                        name=f"{service}-traffic-permission",
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
                                    "action": "Allow",
                                },
                            }
                        ],
                    },
                    opts=ResourceOptions(parent=self, provider=k8s_provider),
                )
                self.permissions.append(service_permission)

        self.register_outputs(
            {
                "default_action": config.traffic_permission_default_action,
                "permission_count": len(self.permissions),
            }
        )
