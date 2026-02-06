"""Zone resources component - ZoneIngress and ZoneEgress for multi-cluster."""

from typing import Optional, List

import pulumi_kubernetes as k8s
from pulumi import ComponentResource, ResourceOptions

from config import KumaConfig, ClusterConfig


class ZoneResources(ComponentResource):
    """Creates ZoneIngress and ZoneEgress resources for multi-zone communication."""

    def __init__(
        self,
        name: str,
        config: KumaConfig,
        k8s_provider: k8s.Provider,
        cluster_config: Optional[ClusterConfig] = None,
        opts: Optional[ResourceOptions] = None,
    ):
        super().__init__("kuma:orchestration:ZoneResources", name, None, opts)

        # Use provided cluster config or get current cluster
        if cluster_config is None:
            cluster_config = config.get_current_cluster()

        zone_name = cluster_config.zone_name
        child_opts = ResourceOptions(parent=self, provider=k8s_provider)

        # ZoneIngress for inbound cross-zone traffic
        self.zone_ingress = None
        if cluster_config.zone_ingress_enabled:
            ingress_spec = {
                "zone": zone_name,
                "networking": {
                    "port": 10001,
                    "advertisedPort": 10001,
                },
            }

            # Add address if specified in cloud provider settings
            if cluster_config.cloud_provider_settings.get("zoneIngressAddress"):
                ingress_spec["networking"]["advertisedAddress"] = cluster_config.cloud_provider_settings["zoneIngressAddress"]

            self.zone_ingress = k8s.apiextensions.CustomResource(
                f"{name}-zone-ingress",
                api_version="kuma.io/v1alpha1",
                kind="ZoneIngress",
                metadata=k8s.meta.v1.ObjectMetaArgs(
                    name=f"{zone_name}-ingress",
                    namespace=config.kuma_namespace,
                    labels={
                        "kuma.io/zone": zone_name,
                        "app.kubernetes.io/name": "zone-ingress",
                        "app.kubernetes.io/instance": zone_name,
                    },
                ),
                spec=ingress_spec,
                opts=child_opts,
            )

        # ZoneEgress for outbound cross-zone traffic
        self.zone_egress = None
        if cluster_config.zone_egress_enabled:
            egress_spec = {
                "zone": zone_name,
                "networking": {
                    "port": 10002,
                },
            }

            self.zone_egress = k8s.apiextensions.CustomResource(
                f"{name}-zone-egress",
                api_version="kuma.io/v1alpha1",
                kind="ZoneEgress",
                metadata=k8s.meta.v1.ObjectMetaArgs(
                    name=f"{zone_name}-egress",
                    namespace=config.kuma_namespace,
                    labels={
                        "kuma.io/zone": zone_name,
                        "app.kubernetes.io/name": "zone-egress",
                        "app.kubernetes.io/instance": zone_name,
                    },
                ),
                spec=egress_spec,
                opts=child_opts,
            )

        # Create zone ingress/egress services for LoadBalancer exposure
        self.zone_ingress_service = None
        self.zone_egress_service = None

        if cluster_config.zone_ingress_enabled and config.is_multi_cluster():
            service_type = "LoadBalancer"
            # Use NodePort for on-prem clusters
            if cluster_config.type.value in ["aks-local", "k3s", "kind"]:
                service_type = "NodePort"

            self.zone_ingress_service = k8s.core.v1.Service(
                f"{name}-zone-ingress-svc",
                metadata=k8s.meta.v1.ObjectMetaArgs(
                    name=f"{zone_name}-zone-ingress",
                    namespace=config.kuma_namespace,
                    labels={
                        "app.kubernetes.io/name": "zone-ingress",
                        "app.kubernetes.io/instance": zone_name,
                    },
                    annotations=_get_lb_annotations(cluster_config),
                ),
                spec=k8s.core.v1.ServiceSpecArgs(
                    type=service_type,
                    ports=[
                        k8s.core.v1.ServicePortArgs(
                            name="zone-ingress",
                            port=10001,
                            target_port=10001,
                            protocol="TCP",
                        ),
                    ],
                    selector={
                        "app.kubernetes.io/name": "kuma-ingress",
                    },
                ),
                opts=child_opts,
            )

        self.register_outputs({
            "zone_name": zone_name,
            "zone_ingress_enabled": cluster_config.zone_ingress_enabled,
            "zone_egress_enabled": cluster_config.zone_egress_enabled,
            "zone_ingress_name": self.zone_ingress.metadata.name if self.zone_ingress else None,
            "zone_egress_name": self.zone_egress.metadata.name if self.zone_egress else None,
        })


def _get_lb_annotations(cluster_config: ClusterConfig) -> dict:
    """Get cloud-specific load balancer annotations."""
    annotations = {}

    if cluster_config.type.value == "eks":
        # AWS NLB for better performance
        annotations["service.beta.kubernetes.io/aws-load-balancer-type"] = "nlb"
        annotations["service.beta.kubernetes.io/aws-load-balancer-scheme"] = "internet-facing"
        annotations["service.beta.kubernetes.io/aws-load-balancer-cross-zone-load-balancing-enabled"] = "true"

    elif cluster_config.type.value == "aks":
        # Azure internal LB if needed
        if cluster_config.cloud_provider_settings.get("internalLoadBalancer") == "true":
            annotations["service.beta.kubernetes.io/azure-load-balancer-internal"] = "true"

    elif cluster_config.type.value == "gke":
        # GCP backend config
        annotations["cloud.google.com/neg"] = '{"ingress": true}'

    return annotations


class MultiZoneResources(ComponentResource):
    """Creates zone resources for multiple clusters."""

    def __init__(
        self,
        name: str,
        config: KumaConfig,
        cluster_providers: dict,  # Dict[str, ClusterProvider]
        opts: Optional[ResourceOptions] = None,
    ):
        super().__init__("kuma:orchestration:MultiZoneResources", name, None, opts)

        self.zone_resources: dict = {}

        for cluster in config.clusters:
            if cluster.name not in cluster_providers:
                continue

            provider = cluster_providers[cluster.name]
            zone_res = ZoneResources(
                f"{name}-{cluster.zone_name}",
                config,
                provider.k8s_provider,
                cluster_config=cluster,
                opts=ResourceOptions(parent=self),
            )
            self.zone_resources[cluster.name] = zone_res

        self.register_outputs({
            "zone_count": len(self.zone_resources),
            "zones": list(self.zone_resources.keys()),
        })
