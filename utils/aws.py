import boto3
import click

client = boto3.client("organizations")


def list_aws_accounts(config) -> list:
    response = client.list_children(
        ParentId=config.ou,
        ChildType="ACCOUNT",
    )

    account_list = [x["Id"] for x in response["Children"]]
    while "NextToken" in response:
        response = client.list_children(
            ParentId=config.ou,
            ChildType="ACCOUNT",
            MaxResults=1,
            NextToken=response["NextToken"],
        )

        temp_list = [x["Id"] for x in response["Children"]]

        account_list += temp_list

    return account_list


def sync_ic_groups(config, account_list) -> object:
    """Creates IC groups for every AWS account ID in the provided list.
    Retreives and return all group IDs, newly and previously created.

    Returns:
        account_id_to_group_id (object): mapping between each account ID, and corresponding IC group ID.
    """
    # Initialize the AWS Identity Store client
    identity_store_client = boto3.client("identitystore")

    account_id_to_group_id = {}

    for group_name in account_list:
        # Check if the group already exists
        try:
            response = identity_store_client.get_group_id(
                IdentityStoreId=config.identity_store_id,
                AlternateIdentifier={
                    "UniqueAttribute": {
                        "AttributePath": "DisplayName",
                        "AttributeValue": group_name,
                    }
                },
            )
            group_id = response["GroupId"]
            account_id_to_group_id[group_name] = group_id

            click.secho(
                f"Group {group_name} already exists (Group ID: {group_id}). Skipping."
            )

        except identity_store_client.exceptions.ResourceNotFoundException:
            # Group doesn't exist, create it
            desc = "Group used to manage access to Hackathon accounts"
            try:
                response = identity_store_client.create_group(
                    IdentityStoreId=config.identity_store_id,
                    DisplayName=group_name,
                    Description=desc,
                )
                group_id = response["GroupId"]
                account_id_to_group_id[group_name] = group_id

                click.echo(f"Created group: {group_name} (Group ID: {group_id})")
            except:
                click.secho(
                    f"Group {group_name} could not be created for some reason. Skipping",
                    fg="red",
                )

    return account_id_to_group_id


def get_sso_instance_arn(config):
    sso_admin_client = boto3.client("sso-admin")

    response = sso_admin_client.list_instances()
    for entry in response["Instances"]:
        if entry["IdentityStoreId"] == config.identity_store_id:
            return entry["InstanceArn"]


def get_permission_set_arn(config, permission_set_name, sso_instance_arn):
    # Initialize the AWS SSO Admin client
    sso_admin_client = boto3.client("sso-admin")

    # List the permission sets to find the ARN of the AWSAdministratorAccess permission set
    response = sso_admin_client.list_permission_sets(InstanceArn=sso_instance_arn)

    # Iterate through the permission sets to find the ARN of the desired permission set
    for permission_set_arn in response["PermissionSets"]:
        response = sso_admin_client.describe_permission_set(
            InstanceArn=sso_instance_arn, PermissionSetArn=permission_set_arn
        )

        if response["PermissionSet"]["Name"] == permission_set_name:
            return permission_set_arn


def associate_group_permissions_with_aws_accounts(
    account_id_to_group_id, permission_set_arn, sso_instance_arn
):
    sso_admin_client = boto3.client("sso-admin")

    for account_id, group_id in account_id_to_group_id.items():
        print(account_id, group_id)

        try:
            sso_admin_client.create_account_assignment(
                InstanceArn=sso_instance_arn,
                PermissionSetArn=permission_set_arn,
                PrincipalId=group_id,
                PrincipalType="GROUP",
                TargetId=account_id,
                TargetType="AWS_ACCOUNT",
            )
        except Exception as e:
            click.secho("e")
    return
