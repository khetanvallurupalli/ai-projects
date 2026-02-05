"""EKS managed add-ons: CoreDNS, kube-proxy, VPC CNI, EBS CSI driver."""

import pulumi
import pulumi_aws as aws

from .irsa import IrsaRole


class EksAddons(pulumi.ComponentResource):
    """Installs EKS managed add-ons with IRSA where required."""

    def __init__(
        self,
        name: str,
        cluster_name: pulumi.Input[str],
        oidc_provider_arn: pulumi.Input[str],
        oidc_issuer: pulumi.Input[str],
        eks_version: str,
        opts: pulumi.ResourceOptions = None,
    ):
        super().__init__("custom:infrastructure:EksAddons", name, {}, opts)

        # --- VPC CNI IRSA ---
        vpc_cni_irsa = IrsaRole(
            f"{name}-vpc-cni",
            oidc_provider_arn=oidc_provider_arn,
            oidc_issuer=oidc_issuer,
            namespace="kube-system",
            service_account_name="aws-node",
            policy_arns=["arn:aws:iam::aws:policy/AmazonEKS_CNI_Policy"],
            opts=pulumi.ResourceOptions(parent=self),
        )

        # --- EBS CSI Driver IRSA ---
        ebs_csi_irsa = IrsaRole(
            f"{name}-ebs-csi",
            oidc_provider_arn=oidc_provider_arn,
            oidc_issuer=oidc_issuer,
            namespace="kube-system",
            service_account_name="ebs-csi-controller-sa",
            policy_arns=[
                "arn:aws:iam::aws:policy/service-role/AmazonEBSCSIDriverPolicy"
            ],
            opts=pulumi.ResourceOptions(parent=self),
        )

        # --- CoreDNS ---
        aws.eks.Addon(
            f"{name}-coredns",
            cluster_name=cluster_name,
            addon_name="coredns",
            resolve_conflicts_on_update="OVERWRITE",
            opts=pulumi.ResourceOptions(parent=self),
        )

        # --- kube-proxy ---
        aws.eks.Addon(
            f"{name}-kube-proxy",
            cluster_name=cluster_name,
            addon_name="kube-proxy",
            resolve_conflicts_on_update="OVERWRITE",
            opts=pulumi.ResourceOptions(parent=self),
        )

        # --- VPC CNI ---
        aws.eks.Addon(
            f"{name}-vpc-cni",
            cluster_name=cluster_name,
            addon_name="vpc-cni",
            service_account_role_arn=vpc_cni_irsa.role_arn,
            resolve_conflicts_on_update="OVERWRITE",
            opts=pulumi.ResourceOptions(parent=self),
        )

        # --- EBS CSI Driver ---
        aws.eks.Addon(
            f"{name}-ebs-csi",
            cluster_name=cluster_name,
            addon_name="aws-ebs-csi-driver",
            service_account_role_arn=ebs_csi_irsa.role_arn,
            resolve_conflicts_on_update="OVERWRITE",
            opts=pulumi.ResourceOptions(parent=self),
        )

        self.register_outputs({})
