import boto3
import click

client = boto3.client("organizations")
identity_store_client = boto3.client("identitystore")
sso_admin_client = boto3.client("sso-admin")


def list_aws_accounts(config) -> list:
    """Lists all AWS accounts in the configured OU

    Returns:
        list: List of AWS accounts
    """
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
        object: mapping between each account ID, and corresponding IC group ID.
    """
    account_id_to_group_id = {}

    with click.progressbar(account_list, label="Syncing") as accounts:
        for group_name in accounts:
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

                if config.verbose:
                    click.secho(
                        f"\nGroup {group_name} already exists (Group ID: {group_id}). Skipping."
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

                    if config.verbose:
                        click.echo(
                            f"\nCreated group: {group_name} (Group ID: {group_id})"
                        )
                except:
                    click.secho(
                        f"Group {group_name} could not be created for some reason. Skipping",
                        fg="red",
                    )

    return account_id_to_group_id


def get_sso_instance_arn(config) -> str:
    """Gets the SSO instance ARN associated to the Identity Store

    Returns:
        str: The SSO instance ARN
    """
    response = sso_admin_client.list_instances()
    for entry in response["Instances"]:
        if entry["IdentityStoreId"] == config.identity_store_id:
            return entry["InstanceArn"]


def get_permission_set_arn(config, permission_set_name, sso_instance_arn) -> str:
    """Returns the permission set ARN given a permission set name"""
    # List the permission sets to find the ARN of the AWSAdministratorAccess permission set
    response = sso_admin_client.list_permission_sets(InstanceArn=sso_instance_arn)

    # Iterate through the permission sets to find the ARN of the desired permission set
    for permission_set_arn in response["PermissionSets"]:
        response = sso_admin_client.describe_permission_set(
            InstanceArn=sso_instance_arn, PermissionSetArn=permission_set_arn
        )

        if response["PermissionSet"]["Name"] == permission_set_name:
            return permission_set_arn
    click.secho(
        f"{permission_set_name} is not an existing permission set name.", fg="red"
    )
    raise Exception("No valid PermissionSet")


def associate_group_permissions_with_aws_accounts(
    config, account_id_to_group_id, permission_set_arn, sso_instance_arn
) -> None:
    """Grant the IC group permission to assume the provided permission set in th corresponding AWS account

    Returns:
        None: The SSO instance ARN
    """
    with click.progressbar(
        account_id_to_group_id.items(), label="Granting group permission"
    ) as mappings:
        for account_id, group_id in mappings:
            try:
                sso_admin_client.create_account_assignment(
                    InstanceArn=sso_instance_arn,
                    PermissionSetArn=permission_set_arn,
                    PrincipalId=group_id,
                    PrincipalType="GROUP",
                    TargetId=account_id,
                    TargetType="AWS_ACCOUNT",
                )
                if config.verbose:
                    click.echo(
                        f"\nGroup {group_id} granted permission to Account {account_id}"
                    )
            except Exception as e:
                raise e
    return


def get_group_ids(config) -> list:
    """Gets the group IDs of the IC groups assosciated with the AWS accounts in the OU

    Returns:
        list: List with the IC group IDs
    """
    account_list = list_aws_accounts(config)

    group_ids = []
    # The IC groups are named using the AWS account ID
    with click.progressbar(account_list, label="Getting group IDs") as accounts:
        for group_name in accounts:
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
                group_ids.append(group_id)

            except Exception as e:
                click.secho(
                    'Something went wrong, fetching the group IDs form the accounts. Perhaps you need to run "hack sync"?',
                    fg="red",
                )
                raise e

    if config.verbose:
        click.secho("Group IDs:")
        click.secho(group_ids)

    return group_ids


def create_sso_users(users):
    """Creates SSO users"""
    pass


def add_users_to_groups():
    """Adds users to IC groups"""
    pass
