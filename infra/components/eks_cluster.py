"""EKS cluster component with managed node groups and OIDC provider."""

from typing import List, Sequence

import pulumi
import pulumi_aws as aws
import pulumi_eks as eks
import pulumi_kubernetes as k8s


class EksCluster(pulumi.ComponentResource):
    """EKS cluster with managed node groups, OIDC provider, and K8s provider."""

    kubeconfig: pulumi.Output
    cluster_name: pulumi.Output[str]
    cluster_endpoint: pulumi.Output[str]
    oidc_provider_arn: pulumi.Output[str]
    oidc_issuer: pulumi.Output[str]
    k8s_provider: k8s.Provider
    cluster: eks.Cluster

    def __init__(
        self,
        name: str,
        vpc_id: pulumi.Input[str],
        private_subnet_ids: pulumi.Input[List[str]],
        public_subnet_ids: pulumi.Input[List[str]],
        cluster_name: str,
        eks_version: str,
        node_instance_types: Sequence[str],
        node_desired_size: int,
        node_min_size: int,
        node_max_size: int,
        public_access: bool = False,
        opts: pulumi.ResourceOptions = None,
    ):
        super().__init__("custom:infrastructure:EksCluster", name, {}, opts)

        # EKS cluster via pulumi_eks high-level component
        self.cluster = eks.Cluster(
            f"{name}-cluster",
            name=cluster_name,
            version=eks_version,
            vpc_id=vpc_id,
            private_subnet_ids=private_subnet_ids,
            public_subnet_ids=public_subnet_ids,
            endpoint_private_access=True,
            endpoint_public_access=public_access,
            instance_type=node_instance_types[0],
            desired_capacity=node_desired_size,
            min_size=node_min_size,
            max_size=node_max_size,
            node_associate_public_ip_address=False,
            create_oidc_provider=True,
            tags={
                "Name": cluster_name,
            },
            opts=pulumi.ResourceOptions(parent=self),
        )

        self.kubeconfig = self.cluster.kubeconfig
        self.cluster_name = pulumi.Output.from_input(cluster_name)
        self.cluster_endpoint = self.cluster.core.apply(
            lambda core: core.endpoint
        )

        # Extract OIDC provider info from the EKS cluster
        self.oidc_provider_arn = self.cluster.core.apply(
            lambda core: core.oidc_provider.arn if core.oidc_provider else ""
        )
        self.oidc_issuer = self.cluster.core.apply(
            lambda core: core.oidc_provider.url if core.oidc_provider else ""
        )

        # Create a K8s provider from the cluster kubeconfig
        self.k8s_provider = k8s.Provider(
            f"{name}-k8s-provider",
            kubeconfig=self.kubeconfig.apply(lambda kc: pulumi.Output.secret(kc) if isinstance(kc, str) else kc),
            opts=pulumi.ResourceOptions(parent=self),
        )

        self.register_outputs(
            {
                "kubeconfig": self.kubeconfig,
                "cluster_name": self.cluster_name,
                "cluster_endpoint": self.cluster_endpoint,
                "oidc_provider_arn": self.oidc_provider_arn,
                "oidc_issuer": self.oidc_issuer,
            }
        )
