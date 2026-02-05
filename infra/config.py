"""Typed configuration loader for the EKS + Kuma + CFK stack."""

from dataclasses import dataclass, field
from typing import List

import pulumi


@dataclass
class StackConfig:
    """All stack configuration values loaded from Pulumi config."""

    environment: str
    aws_region: str
    vpc_id: str
    public_subnet_ids: List[str]
    private_subnet_ids: List[str]

    # EKS
    eks_cluster_name: str
    eks_version: str
    node_instance_types: List[str]
    node_desired_size: int
    node_min_size: int
    node_max_size: int
    eks_public_access: bool

    # Helm chart versions
    kuma_version: str
    cfk_version: str

    # Confluent Cloud (secrets)
    confluent_cloud_bootstrap: str
    confluent_cloud_api_key: pulumi.Output
    confluent_cloud_api_secret: pulumi.Output


def load_config() -> StackConfig:
    """Load and return typed configuration from Pulumi config."""
    cfg = pulumi.Config()
    aws_cfg = pulumi.Config("aws")

    return StackConfig(
        environment=cfg.require("environment"),
        aws_region=aws_cfg.require("region"),
        vpc_id=cfg.require("vpcId"),
        public_subnet_ids=cfg.require_object("publicSubnetIds"),
        private_subnet_ids=cfg.require_object("privateSubnetIds"),
        eks_cluster_name=cfg.require("eksClusterName"),
        eks_version=cfg.get("eksVersion") or "1.29",
        node_instance_types=cfg.require_object("nodeInstanceTypes"),
        node_desired_size=cfg.get_int("nodeDesiredSize") or 2,
        node_min_size=cfg.get_int("nodeMinSize") or 1,
        node_max_size=cfg.get_int("nodeMaxSize") or 5,
        eks_public_access=cfg.get_bool("eksPublicAccess") or False,
        kuma_version=cfg.get("kumaVersion") or "2.9.1",
        cfk_version=cfg.get("cfkVersion") or "0.1033.3",
        confluent_cloud_bootstrap=cfg.require("confluentCloudBootstrap"),
        confluent_cloud_api_key=cfg.require_secret("confluentCloudApiKey"),
        confluent_cloud_api_secret=cfg.require_secret("confluentCloudApiSecret"),
    )
