"""Zone resources component - ZoneIngress and ZoneEgress."""

from typing import Optional

import pulumi_kubernetes as k8s
from pulumi import ComponentResource, ResourceOptions

from config import KumaConfig


class ZoneResources(ComponentResource):
    """Creates ZoneIngress and ZoneEgress resources for multi-zone communication."""

    def __init__(
        self,
        name: str,
        config: KumaConfig,
        k8s_provider: k8s.Provider,
        opts: Optional[ResourceOptions] = None,
    ):
        super().__init__("kuma:orchestration:ZoneResources", name, None, opts)

        # ZoneIngress for inbound cross-zone traffic
        self.zone_ingress = k8s.apiextensions.CustomResource(
            f"{name}-zone-ingress",
            api_version="kuma.io/v1alpha1",
            kind="ZoneIngress",
            metadata=k8s.meta.v1.ObjectMetaArgs(
                name=f"{config.kuma_zone_name}-ingress",
                namespace=config.kuma_namespace,
                labels={
                    "kuma.io/zone": config.kuma_zone_name,
                },
            ),
            spec={
                "zone": config.kuma_zone_name,
                "networking": {
                    "address": "",  # Auto-assigned
                    "port": 10001,
                    "advertisedAddress": "",
                    "advertisedPort": 10001,
                },
            },
            opts=ResourceOptions(parent=self, provider=k8s_provider),
        )

        # ZoneEgress for outbound cross-zone traffic
        self.zone_egress = k8s.apiextensions.CustomResource(
            f"{name}-zone-egress",
            api_version="kuma.io/v1alpha1",
            kind="ZoneEgress",
            metadata=k8s.meta.v1.ObjectMetaArgs(
                name=f"{config.kuma_zone_name}-egress",
                namespace=config.kuma_namespace,
                labels={
                    "kuma.io/zone": config.kuma_zone_name,
                },
            ),
            spec={
                "zone": config.kuma_zone_name,
                "networking": {
                    "address": "",  # Auto-assigned
                    "port": 10002,
                },
            },
            opts=ResourceOptions(parent=self, provider=k8s_provider),
        )

        self.register_outputs(
            {
                "zone_ingress_name": self.zone_ingress.metadata.name,
                "zone_egress_name": self.zone_egress.metadata.name,
            }
        )
