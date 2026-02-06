"""Cluster provider abstractions for multi-cluster support."""

from typing import Optional, Dict, Any
from abc import ABC, abstractmethod

import pulumi
import pulumi_kubernetes as k8s
from pulumi import ComponentResource, ResourceOptions, Output

from config import KumaConfig, ClusterConfig, ClusterType


class ClusterProvider(ComponentResource, ABC):
    """Abstract base class for cluster providers."""

    k8s_provider: k8s.Provider
    cluster_name: Output[str]
    cluster_endpoint: Output[str]

    def __init__(
        self,
        name: str,
        cluster_config: ClusterConfig,
        opts: Optional[ResourceOptions] = None,
    ):
        super().__init__(
            f"kuma:orchestration:ClusterProvider:{cluster_config.type.value}",
            name,
            None,
            opts,
        )
        self.cluster_config = cluster_config

    @abstractmethod
    def get_kubeconfig(self) -> Output[str]:
        """Get the kubeconfig for this cluster."""
        pass


class EKSClusterProvider(ClusterProvider):
    """Provider for Amazon EKS clusters."""

    def __init__(
        self,
        name: str,
        cluster_config: ClusterConfig,
        opts: Optional[ResourceOptions] = None,
    ):
        super().__init__(name, cluster_config, opts)

        if cluster_config.infra_stack_name:
            # Get kubeconfig from stack reference
            self.infra_stack = pulumi.StackReference(
                f"{name}-infra-ref",
                stack_name=cluster_config.infra_stack_name,
                opts=ResourceOptions(parent=self),
            )
            self.kubeconfig = self.infra_stack.get_output("kubeconfig")
            self.cluster_name = self.infra_stack.get_output("cluster_name")
            self.cluster_endpoint = self.infra_stack.get_output("cluster_endpoint")
        elif cluster_config.kubeconfig_secret_name:
            # Get kubeconfig from Kubernetes secret (for external clusters)
            self.kubeconfig = pulumi.Config().require_secret(cluster_config.kubeconfig_secret_name)
            self.cluster_name = Output.from_input(cluster_config.name)
            self.cluster_endpoint = Output.from_input("")
        else:
            raise ValueError(f"Cluster {cluster_config.name} requires either infraStackName or kubeconfigSecretName")

        self.k8s_provider = k8s.Provider(
            f"{name}-k8s-provider",
            kubeconfig=self.kubeconfig,
            opts=ResourceOptions(parent=self),
        )

        self.register_outputs({
            "cluster_name": self.cluster_name,
            "cluster_endpoint": self.cluster_endpoint,
        })

    def get_kubeconfig(self) -> Output[str]:
        return self.kubeconfig


class AKSClusterProvider(ClusterProvider):
    """Provider for Azure AKS clusters."""

    def __init__(
        self,
        name: str,
        cluster_config: ClusterConfig,
        opts: Optional[ResourceOptions] = None,
    ):
        super().__init__(name, cluster_config, opts)

        if cluster_config.infra_stack_name:
            # Get kubeconfig from stack reference
            self.infra_stack = pulumi.StackReference(
                f"{name}-infra-ref",
                stack_name=cluster_config.infra_stack_name,
                opts=ResourceOptions(parent=self),
            )
            self.kubeconfig = self.infra_stack.get_output("kubeconfig")
            self.cluster_name = self.infra_stack.get_output("cluster_name")
            self.cluster_endpoint = self.infra_stack.get_output("cluster_fqdn")
        elif cluster_config.kubeconfig_secret_name:
            self.kubeconfig = pulumi.Config().require_secret(cluster_config.kubeconfig_secret_name)
            self.cluster_name = Output.from_input(cluster_config.name)
            self.cluster_endpoint = Output.from_input("")
        else:
            raise ValueError(f"Cluster {cluster_config.name} requires either infraStackName or kubeconfigSecretName")

        self.k8s_provider = k8s.Provider(
            f"{name}-k8s-provider",
            kubeconfig=self.kubeconfig,
            opts=ResourceOptions(parent=self),
        )

        self.register_outputs({
            "cluster_name": self.cluster_name,
            "cluster_endpoint": self.cluster_endpoint,
        })

    def get_kubeconfig(self) -> Output[str]:
        return self.kubeconfig


class AKSLocalClusterProvider(ClusterProvider):
    """Provider for Azure Arc-enabled AKS on-premises clusters (AKS Local/HCI)."""

    def __init__(
        self,
        name: str,
        cluster_config: ClusterConfig,
        opts: Optional[ResourceOptions] = None,
    ):
        super().__init__(name, cluster_config, opts)

        # AKS Local clusters typically use kubeconfig from secret
        if cluster_config.kubeconfig_secret_name:
            self.kubeconfig = pulumi.Config().require_secret(cluster_config.kubeconfig_secret_name)
        elif cluster_config.infra_stack_name:
            self.infra_stack = pulumi.StackReference(
                f"{name}-infra-ref",
                stack_name=cluster_config.infra_stack_name,
                opts=ResourceOptions(parent=self),
            )
            self.kubeconfig = self.infra_stack.get_output("kubeconfig")
        else:
            raise ValueError(f"Cluster {cluster_config.name} requires either infraStackName or kubeconfigSecretName")

        self.cluster_name = Output.from_input(cluster_config.name)
        self.cluster_endpoint = Output.from_input(
            cluster_config.cloud_provider_settings.get("apiServerEndpoint", "")
        )

        self.k8s_provider = k8s.Provider(
            f"{name}-k8s-provider",
            kubeconfig=self.kubeconfig,
            opts=ResourceOptions(parent=self),
        )

        self.register_outputs({
            "cluster_name": self.cluster_name,
            "cluster_endpoint": self.cluster_endpoint,
        })

    def get_kubeconfig(self) -> Output[str]:
        return self.kubeconfig


class GKEClusterProvider(ClusterProvider):
    """Provider for Google GKE clusters."""

    def __init__(
        self,
        name: str,
        cluster_config: ClusterConfig,
        opts: Optional[ResourceOptions] = None,
    ):
        super().__init__(name, cluster_config, opts)

        if cluster_config.infra_stack_name:
            self.infra_stack = pulumi.StackReference(
                f"{name}-infra-ref",
                stack_name=cluster_config.infra_stack_name,
                opts=ResourceOptions(parent=self),
            )
            self.kubeconfig = self.infra_stack.get_output("kubeconfig")
            self.cluster_name = self.infra_stack.get_output("cluster_name")
            self.cluster_endpoint = self.infra_stack.get_output("cluster_endpoint")
        elif cluster_config.kubeconfig_secret_name:
            self.kubeconfig = pulumi.Config().require_secret(cluster_config.kubeconfig_secret_name)
            self.cluster_name = Output.from_input(cluster_config.name)
            self.cluster_endpoint = Output.from_input("")
        else:
            raise ValueError(f"Cluster {cluster_config.name} requires either infraStackName or kubeconfigSecretName")

        self.k8s_provider = k8s.Provider(
            f"{name}-k8s-provider",
            kubeconfig=self.kubeconfig,
            opts=ResourceOptions(parent=self),
        )

        self.register_outputs({
            "cluster_name": self.cluster_name,
            "cluster_endpoint": self.cluster_endpoint,
        })

    def get_kubeconfig(self) -> Output[str]:
        return self.kubeconfig


class GenericClusterProvider(ClusterProvider):
    """Generic provider for other cluster types (KIND, K3s, Rancher, OpenShift)."""

    def __init__(
        self,
        name: str,
        cluster_config: ClusterConfig,
        opts: Optional[ResourceOptions] = None,
    ):
        super().__init__(name, cluster_config, opts)

        if cluster_config.kubeconfig_secret_name:
            self.kubeconfig = pulumi.Config().require_secret(cluster_config.kubeconfig_secret_name)
        elif cluster_config.infra_stack_name:
            self.infra_stack = pulumi.StackReference(
                f"{name}-infra-ref",
                stack_name=cluster_config.infra_stack_name,
                opts=ResourceOptions(parent=self),
            )
            self.kubeconfig = self.infra_stack.get_output("kubeconfig")
        else:
            raise ValueError(f"Cluster {cluster_config.name} requires either infraStackName or kubeconfigSecretName")

        self.cluster_name = Output.from_input(cluster_config.name)
        self.cluster_endpoint = Output.from_input("")

        self.k8s_provider = k8s.Provider(
            f"{name}-k8s-provider",
            kubeconfig=self.kubeconfig,
            opts=ResourceOptions(parent=self),
        )

        self.register_outputs({
            "cluster_name": self.cluster_name,
            "cluster_endpoint": self.cluster_endpoint,
        })

    def get_kubeconfig(self) -> Output[str]:
        return self.kubeconfig


def create_cluster_provider(
    name: str,
    cluster_config: ClusterConfig,
    opts: Optional[ResourceOptions] = None,
) -> ClusterProvider:
    """Factory function to create the appropriate cluster provider."""
    providers = {
        ClusterType.EKS: EKSClusterProvider,
        ClusterType.AKS: AKSClusterProvider,
        ClusterType.AKS_LOCAL: AKSLocalClusterProvider,
        ClusterType.GKE: GKEClusterProvider,
        ClusterType.KIND: GenericClusterProvider,
        ClusterType.K3S: GenericClusterProvider,
        ClusterType.OPENSHIFT: GenericClusterProvider,
        ClusterType.RANCHER: GenericClusterProvider,
    }

    provider_class = providers.get(cluster_config.type, GenericClusterProvider)
    return provider_class(name, cluster_config, opts)


class MultiClusterManager(ComponentResource):
    """Manages multiple cluster providers for multi-cluster deployments."""

    def __init__(
        self,
        name: str,
        config: KumaConfig,
        opts: Optional[ResourceOptions] = None,
    ):
        super().__init__("kuma:orchestration:MultiClusterManager", name, None, opts)

        self.providers: Dict[str, ClusterProvider] = {}
        self.config = config

        # Create provider for each cluster
        for cluster in config.clusters:
            provider = create_cluster_provider(
                f"{name}-{cluster.name}",
                cluster,
                opts=ResourceOptions(parent=self),
            )
            self.providers[cluster.name] = provider

        self.register_outputs({
            "cluster_count": len(self.providers),
            "cluster_names": list(self.providers.keys()),
        })

    def get_provider(self, cluster_name: str) -> ClusterProvider:
        """Get the provider for a specific cluster."""
        if cluster_name not in self.providers:
            raise ValueError(f"Cluster '{cluster_name}' not found")
        return self.providers[cluster_name]

    def get_current_provider(self) -> ClusterProvider:
        """Get the provider for the current cluster context."""
        return self.get_provider(self.config.current_cluster_name)

    def get_global_cp_provider(self) -> Optional[ClusterProvider]:
        """Get the provider for the global control plane cluster."""
        global_cluster = self.config.get_global_cp_cluster()
        if global_cluster:
            return self.get_provider(global_cluster.name)
        return None
