"""IRSA (IAM Roles for Service Accounts) helper component."""

from typing import List

import pulumi
import pulumi_aws as aws


class IrsaRole(pulumi.ComponentResource):
    """Creates an IAM role bound to a Kubernetes ServiceAccount via OIDC federation."""

    role_arn: pulumi.Output[str]
    role: aws.iam.Role

    def __init__(
        self,
        name: str,
        oidc_provider_arn: pulumi.Input[str],
        oidc_issuer: pulumi.Input[str],
        namespace: str,
        service_account_name: str,
        policy_arns: List[str] = None,
        inline_policy_doc: pulumi.Input[str] = None,
        opts: pulumi.ResourceOptions = None,
    ):
        super().__init__("custom:infrastructure:IrsaRole", name, {}, opts)

        # Build the trust policy for OIDC federation
        assume_role_policy = pulumi.Output.all(
            oidc_provider_arn, oidc_issuer
        ).apply(
            lambda args: aws.iam.get_policy_document(
                statements=[
                    {
                        "effect": "Allow",
                        "principals": [
                            {
                                "type": "Federated",
                                "identifiers": [args[0]],
                            }
                        ],
                        "actions": ["sts:AssumeRoleWithWebIdentity"],
                        "conditions": [
                            {
                                "test": "StringEquals",
                                "variable": f"{args[1]}:sub",
                                "values": [
                                    f"system:serviceaccount:{namespace}:{service_account_name}"
                                ],
                            },
                            {
                                "test": "StringEquals",
                                "variable": f"{args[1]}:aud",
                                "values": ["sts.amazonaws.com"],
                            },
                        ],
                    }
                ]
            ).json
        )

        self.role = aws.iam.Role(
            f"{name}-role",
            assume_role_policy=assume_role_policy,
            tags={"Name": f"{name}-irsa"},
            opts=pulumi.ResourceOptions(parent=self),
        )
        self.role_arn = self.role.arn

        # Attach managed policies
        if policy_arns:
            for i, arn in enumerate(policy_arns):
                aws.iam.RolePolicyAttachment(
                    f"{name}-policy-{i}",
                    role=self.role.name,
                    policy_arn=arn,
                    opts=pulumi.ResourceOptions(parent=self),
                )

        # Attach inline policy if provided
        if inline_policy_doc is not None:
            aws.iam.RolePolicy(
                f"{name}-inline-policy",
                role=self.role.name,
                policy=inline_policy_doc,
                opts=pulumi.ResourceOptions(parent=self),
            )

        self.register_outputs({"role_arn": self.role_arn})
