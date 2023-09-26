import click
import sys
from utils.cli import *
from utils.aws import *
import json


class Config(object):
    """
    A configuration class that holds the verbose mode and updates the configuration
    from the configuration file.
    """

    def __init__(self) -> None:
        """
        Initialize the configuration object and update it from the configuration file.
        """
        self.verbose = False
        self.update_from_conf_file()

    ALLOWED_KEYS = ['verbose', 'region', 'ou', 'identity_store_id']

    # Merge existing conf with Config object
    def update_from_conf_file(self):
        conf = get_configuration()
        if conf:
            for key, value in conf.items():
                if key in self.ALLOWED_KEYS:
                    setattr(self, key, value)


pass_config = click.make_pass_decorator(Config, ensure=True)


@click.group()
@click.option("-v", "--verbose", is_flag=True)
@pass_config
def cli(config, verbose):
    config.verbose = verbose


@cli.command()
def configure():
    """Configures the hackathon CLI with relevant information"""
    region = click.prompt(
        "What AWS region do you want to use?", type=str, default="eu-north-1"
    )
    click.echo(
        "This tools requires all AWS accounts used for hackathons to be in the same Organizational Unit."
    )

    ou = ""

    while not ou.startswith("ou-"):
        if ou:
            click.secho("That's not the OU ID, and you know it", fg="red")
        ou = click.prompt("Enter the ID of the OU", type=str)

    identity_store_id = click.prompt("Enter the Identity Store ID", type=str)

    store_configuration(
        {"region": region, "ou": ou, "identity_store_id": identity_store_id}
    )

    click.secho("\n\U0001F973 hack cli is now ready to be used", fg="cyan")
    click.secho(
        '\nIf you ever need to reconfigure the cli, just run "hack configure"',
        fg="white",
    )


@cli.command()
@pass_config
@require_cli_config
def get_conf():
    """Prints current configuration"""
    click.secho(json.dumps(get_configuration(), indent=3), fg="cyan")


@cli.command()
@pass_config
@require_cli_config
def list_accounts(config):
    """List AWS accounts designated for hackathons"""
    account_list = list_aws_accounts(config)
    click.secho(f"There are {len(account_list)} AWS accounts in the OU:")
    for account in account_list:
        click.secho(account)


@cli.command()
@pass_config
@require_cli_config
@click.option(
    "-p",
    "--permission-set-name",
    type=str,
    default="AWSAdministratorAccess",
    show_default=True,
    help="Name of permission set to grant groups access to",
)
def sync_groups(config, permission_set_name):
    """Syncs Identity Center (IC) groups and AWS Accounts.
    Ensures one IC Group is created for each AWS account, and that that
    group is granted access to the Administrator permission set for the corresponding AWS account.
    """

    # Each group is granted access to this permission set in the corresponding accounts.
    permission_set_name = "AWSAdministratorAccess"

    # Get all AWS accounts in hackathon OU
    account_list = list_aws_accounts(config)

    # For each AWS account, ensures there's an IC group with the same name (Account ID)
    account_id_to_group_id = sync_ic_groups(config, account_list)

    # This is what the SSO Admin client needs to perform administrative tasks...
    sso_instance_arn = get_sso_instance_arn(config)

    # Get the ARN of the desired permission set.
    permission_set_arn = get_permission_set_arn(
        config, permission_set_name, sso_instance_arn
    )

    click.echo(
        f"Granting the IC groups permission to assume the {permission_set_name} permission set in the corresponding accounts..."
    )
    # Ensures that every group has an assosciation to the admin permission set in the corresponding AWS account.
    # That mean that adding a user to an IC group, automatically grants that user admin permission to that AWS account.
    associate_group_permissions_with_aws_accounts(
        config, account_id_to_group_id, permission_set_arn, sso_instance_arn
    )


@cli.command()
@pass_config
@require_cli_config
def delete_groups(config):
    """Deletes all IC groups, to reset all permission sets."""

    # Get all AWS accounts in hackathon OU
    account_list = list_aws_accounts(config)

    # Gets the group IDs associated with the AWS accounts
    group_ids = get_group_ids(config, account_list)

    delete_ic_groups(config, group_ids)

    click.secho(
        f"\nAll IC groups and associations deleted. To recreate them, run 'hack sync' ",
        fg="cyan",
    )


@cli.command()
@pass_config
@require_cli_config
@click.argument("path", type=click.Path(exists=True))
@click.option(
    "-t",
    "--type",
    type=str,
    default="hackathon",
    show_default=True,
    help="Specify user type. Helpfull for batch-operations down the line.",
)
def setup_users(config, path, type):
    """Creates and syncs IC users with their respective team groups"""

    users = get_users(config, path)
    click.echo(json.dumps(users, indent=2))

    # Get all AWS accounts in hackathon OU
    account_list = list_aws_accounts(config)

    group_ids = get_group_ids(config, account_list)

    users = create_sso_users(config, users, type)
    click.echo(json.dumps(users, indent=2))

    add_users_to_groups(config, users, group_ids)

    click.secho(
        "\nUsers have been addded to the respective groups, and should now have access to their AWS accounts",
        fg="cyan",
    )
