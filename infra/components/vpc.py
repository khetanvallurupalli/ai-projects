"""VPC lookup component — imports an existing VPC and subnets by ID."""

from typing import List, Sequence

import pulumi
import pulumi_aws as aws


class VpcLookup(pulumi.ComponentResource):
    """Looks up an existing VPC and its subnets by ID. No resources are created."""

    vpc_id: pulumi.Output[str]
    public_subnet_ids: pulumi.Output[List[str]]
    private_subnet_ids: pulumi.Output[List[str]]

    def __init__(
        self,
        name: str,
        vpc_id: str,
        public_subnet_ids: Sequence[str],
        private_subnet_ids: Sequence[str],
        opts: pulumi.ResourceOptions = None,
    ):
        super().__init__("custom:infrastructure:VpcLookup", name, {}, opts)

        # Look up the existing VPC to validate it exists
        existing_vpc = aws.ec2.get_vpc(id=vpc_id)

        self.vpc_id = pulumi.Output.from_input(existing_vpc.id)
        self.public_subnet_ids = pulumi.Output.from_input(list(public_subnet_ids))
        self.private_subnet_ids = pulumi.Output.from_input(list(private_subnet_ids))

        self.register_outputs(
            {
                "vpc_id": self.vpc_id,
                "public_subnet_ids": self.public_subnet_ids,
                "private_subnet_ids": self.private_subnet_ids,
            }
        )
