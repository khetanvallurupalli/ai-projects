"""Cluster reference component - reads EKS outputs from infra stack."""

from typing import Optional

import pulumi
import pulumi_kubernetes as k8s
from pulumi import ComponentResource, ResourceOptions

from config import KumaConfig


class ClusterReference(ComponentResource):
    """References an existing EKS cluster from the infra stack."""

    def __init__(
        self,
        name: str,
        config: KumaConfig,
        opts: Optional[ResourceOptions] = None,
    ):
        super().__init__("kuma:orchestration:ClusterReference", name, None, opts)

        # Get stack reference to infra project
        self.infra_stack = pulumi.StackReference(
            f"{name}-infra-ref",
            stack_name=config.infra_stack_name,
            opts=ResourceOptions(parent=self),
        )

        # Read outputs from infra stack
        self.kubeconfig = self.infra_stack.get_output("kubeconfig")
        self.cluster_name = self.infra_stack.get_output("cluster_name")
        self.cluster_endpoint = self.infra_stack.get_output("cluster_endpoint")
        self.cluster_ca_data = self.infra_stack.get_output("cluster_ca_data")

        # Create K8s provider from kubeconfig
        self.k8s_provider = k8s.Provider(
            f"{name}-k8s-provider",
            kubeconfig=self.kubeconfig,
            opts=ResourceOptions(parent=self),
        )

        self.register_outputs(
            {
                "cluster_name": self.cluster_name,
                "cluster_endpoint": self.cluster_endpoint,
            }
        )
