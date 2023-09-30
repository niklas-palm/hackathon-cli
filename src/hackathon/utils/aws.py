import boto3
import click
import json

org_client = boto3.client("organizations")
identity_store_client = boto3.client("identitystore")
sso_admin_client = boto3.client("sso-admin")


def list_aws_accounts(config: object) -> list:
    """Lists all AWS accounts in the configured OU

    Parameters:
        config (object): CLI configuration object.

    Returns:
        list: List of AWS accounts
    """

    click.echo("Getting AWS account IDs from Hackathon OU...")

    response = org_client.list_children(
        ParentId=config.ou,
        ChildType="ACCOUNT",
    )

    account_list = [x["Id"] for x in response["Children"]]
    while "NextToken" in response:
        response = org_client.list_children(
            ParentId=config.ou,
            ChildType="ACCOUNT",
            MaxResults=1,
            NextToken=response["NextToken"],
        )

        temp_list = [x["Id"] for x in response["Children"]]

        account_list += temp_list

    return account_list


def sync_ic_groups(config: object, account_list: list) -> object:
    """Creates IC groups for every AWS account ID in the provided list.
    Retreives and return all group IDs, newly and previously created.

    Parameters:
        config (object): CLI configuration object.
        account_list (list): list of AWS accounts.

    Returns:
        object: mapping between each account ID, and corresponding IC group ID.
    """

    click.echo(
        "Ensuring there's an IC group for each AWS Account. Creating if it's missing..."
    )

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


def delete_ic_groups(conf: object, group_ids: list) -> None:
    """Deletes the Identity Center groups

    Parameters:
        config (object): CLI configuration object.
        group_ids (list): list of IC group IDs to delete

    Returns:
        None
    """

    with click.progressbar(group_ids, label="Deleting IC Groups") as groups:
        for group_id in groups:
            try:
                identity_store_client.delete_group(
                    IdentityStoreId=conf.identity_store_id, GroupId=group_id
                )
            except Exception as e:
                click.secho("There was some issue deleteing the IC group", fg="red")
                raise e


def get_sso_instance_arn(config) -> str:
    """Gets the SSO instance ARN associated to the Identity Store

    Parameters:
        config (object): CLI configuration object.
        account_id_to_group_id (object): AWS Account ID to IC group ID mapping.
        permission_set_arn (str): ARN of permission set to grant group acccess to.
        sso_instance_arn (str): ARN of SSO instance.

    Returns:
        str: the ARN of the SSO instance
    """
    response = sso_admin_client.list_instances()
    for entry in response["Instances"]:
        if entry["IdentityStoreId"] == config.identity_store_id:
            return entry["InstanceArn"]


def get_permission_set_arn(
    config: object, permission_set_name: str, sso_instance_arn: str
) -> str:
    """Returns the permission set ARN given a permission set name"""
    # List the permission sets to find the ARN of the AWSAdministratorAccess permission set

    if config.verbose:
        click.echo("Getting Permission set ARN...")

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
    config: object,
    account_id_to_group_id: object,
    permission_set_arn: str,
    sso_instance_arn: str,
) -> None:
    """Grant the IC group permission to assume the provided permission set in th corresponding AWS account

    Parameters:
        config (object): CLI configuration object.
        account_id_to_group_id (object): AWS Account ID to IC group ID mapping.
        permission_set_arn (str): ARN of permission set to grant group acccess to.
        sso_instance_arn (str): ARN of SSO instance.

    Returns:
        None:
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


def get_group_ids(config: object, account_list: list) -> list:
    """Gets the group IDs of the IC groups assosciated with the AWS accounts in the OU

    Parameters:
        config (object): CLI configuration object
        account_list (list): list with AWS account IDs to find corresponding IC groups for

    Returns:
        list: List with the IC group IDs
    """

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

            except identity_store_client.exceptions.ResourceNotFoundException:
                # No IC groupt with this ID
                continue

            except Exception as e:
                click.secho(
                    '\nSomething went wrong, fetching the group IDs form the accounts. Perhaps you need to run "hack sync-groups"?',
                    fg="red",
                )
                raise e

    if config.verbose:
        click.secho("Group IDs:")
        click.secho(group_ids)

    return group_ids


def create_sso_users(config: object, users: object, user_type: str) -> object:
    """Creates IC users

    Parameters:
        config (object): CLI configuration object
        users (object): Dictionary on shape {email: {team: '1'}}
        path (str): path to user csv file

    Returns:
        object: a user object on shape {user_email: {team: '1', user_id: '34543sdf'}}
    """

    click.echo("Creating/Fetching IC users")

    with click.progressbar(users.keys(), label="Creating IC users") as user_emails:
        for user_email in user_emails:
            try:
                response = identity_store_client.get_user_id(
                    IdentityStoreId=config.identity_store_id,
                    AlternateIdentifier={
                        "UniqueAttribute": {
                            "AttributePath": "userName",
                            "AttributeValue": user_email,
                        }
                    },
                )
                if config.verbose:
                    click.echo(f"\nUser with email {user_email} already exists.")

                users[user_email]["user_id"] = response["UserId"]
            except identity_store_client.exceptions.ResourceNotFoundException:
                # User not found, creating user
                try:
                    response = identity_store_client.create_user(
                        IdentityStoreId=config.identity_store_id,
                        UserName=user_email,
                        DisplayName=user_email,
                        Name={"GivenName": "John", "FamilyName": "Doe"},
                        Emails=[
                            {
                                "Value": user_email,
                                "Type": "Work",
                                "Primary": True,
                            },
                        ],
                        UserType=user_type,
                    )
                    if config.verbose:
                        click.echo(f"\nNew user with email {user_email} created")

                    users[user_email]["user_id"] = response["UserId"]
                except Exception as e:
                    click.echo(
                        f"\nSomething went wrong when trying to add user {user_email}",
                        fg="red",
                    )
                    raise e
    return users


def add_users_to_groups(config: object, users: object, group_ids: list) -> None:
    """Adds users to IC groups

    Parameters:
        config (object): CLI configuration object
        users (object): Dictionary on shape {user_email: {team: '1', user_id: '34543sdf'}}
        path (str): path to user csv file

    Returns:
        None
    """

    click.echo("Adding users to respective team IC groups.")

    # Create team number to group mapping.
    teams = [x["team"] for x in users.values()]
    unique_teams = list(set(teams))
    team_to_group_mapping = dict(zip(unique_teams, group_ids))

    with click.progressbar(users.items(), label="Adding users to groups") as user_items:
        for email, user_info in user_items:
            team = user_info["team"]
            user_id = user_info["user_id"]

            try:
                identity_store_client.create_group_membership(
                    IdentityStoreId=config.identity_store_id,
                    GroupId=team_to_group_mapping[team],
                    MemberId={"UserId": user_id},
                )

            except identity_store_client.exceptions.ConflictException:
                # User already in group
                pass
            except Exception as e:
                click.echo(
                    f"\nSomething went wrong when trying to add user {email} to IC group {team_to_group_mapping[team]}",
                    fg="red",
                )
                raise e


def list_users(config: object) -> list:
    """Fetches all users from Identy Center

    Parameters:
        config (object): CLI configuration object

    Returns:
        list: list of IC users
    """
    user_list = []
    try:
        response = identity_store_client.list_users(
            IdentityStoreId=config.identity_store_id,
            # NextToken='string',
            # Filters=[
            #     {"AttributePath": "UserType", "AttributeValue": "type"},
            # ],
        )
        user_list += response["Users"]

        while "NextToken" in response:
            response = identity_store_client.list_users(
                IdentityStoreId=config.identity_store_id,
                NextToken=response["NextToken"],
            )

            user_list += response["Users"]

    except Exception as e:
        click.secho("Something went wrong when fetching users...")
        click.echo(e)

    return user_list


def get_users_of_type(config: object, user_type: str) -> list:
    """Fetches all users in Identity Center of the provided user type

    Parameters:
        config (object): CLI configuration object
        type (str): UserType

    Returns:
        list: list of IC users of given UserType
    """
    users = list_users(config)

    # Extract users that matches the type
    return [x for x in users if "UserType" in x and x["UserType"] == user_type]


def delete_users(config: object, users: list) -> None:
    if users:
        for user in users:
            try:
                identity_store_client.delete_user(
                    IdentityStoreId=config.identity_store_id,
                    UserId=user["UserId"],
                )

                click.secho(f"{user['DisplayName']} deleted", fg="green")
            except Exception as e:
                click.secho(
                    f"Something went wrong when deleting user: \n{json.dumps(user, indent=2)}",
                    fg="red",
                )
                raise e
    else:
        click.secho("\nNo users found that matched the UserType\n", fg="red")
