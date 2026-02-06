"""Fault injection component - MeshFaultInjection (dev only)."""

from typing import List, Optional

import pulumi_kubernetes as k8s
from pulumi import ComponentResource, ResourceOptions

from config import KumaConfig


class FaultInjection(ComponentResource):
    """Creates MeshFaultInjection policies for testing (dev only)."""

    def __init__(
        self,
        name: str,
        config: KumaConfig,
        k8s_provider: k8s.Provider,
        opts: Optional[ResourceOptions] = None,
    ):
        super().__init__("kuma:orchestration:FaultInjection", name, None, opts)

        self.fault_injections: List[k8s.apiextensions.CustomResource] = []

        # Only create fault injection in dev when enabled
        if not config.fault_injection_enabled:
            self.register_outputs(
                {
                    "enabled": False,
                    "fault_injection_count": 0,
                }
            )
            return

        # Create MeshFaultInjection for each managed service
        for service in config.managed_services:
            fault_injection = k8s.apiextensions.CustomResource(
                f"{name}-fault-injection-{service}",
                api_version="kuma.io/v1alpha1",
                kind="MeshFaultInjection",
                metadata=k8s.meta.v1.ObjectMetaArgs(
                    name=f"{service}-fault-injection",
                    namespace=config.kuma_namespace,
                    labels={
                        "kuma.io/mesh": config.mesh_name,
                        "kuma.io/origin": "zone",
                        "app": service,
                        "environment": "dev",
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
                                "http": [
                                    {
                                        "abort": {
                                            "httpStatus": 503,
                                            "percentage": str(config.fault_injection_abort_percent),
                                        },
                                    },
                                    {
                                        "delay": {
                                            "value": f"{config.fault_injection_delay_ms}ms",
                                            "percentage": str(config.fault_injection_delay_percent),
                                        },
                                    },
                                ],
                            },
                        }
                    ],
                },
                opts=ResourceOptions(parent=self, provider=k8s_provider),
            )
            self.fault_injections.append(fault_injection)

        self.register_outputs(
            {
                "enabled": True,
                "fault_injection_count": len(self.fault_injections),
                "abort_percent": config.fault_injection_abort_percent,
                "delay_percent": config.fault_injection_delay_percent,
            }
        )
