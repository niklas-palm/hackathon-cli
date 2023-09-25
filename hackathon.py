import click
from utils.cli import *
from utils.aws import *
import json


class Config(object):
    def __init__(self) -> None:
        self.verbose = False
        self.update_from_conf_file()

    # Merge existing conf with Config object
    def update_from_conf_file(self):
        conf = get_configuration()
        if conf:
            for key, value in conf.items():
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

    click.secho(f"\n\U0001F973 hack cli is now ready to be used", fg="cyan")
    click.secho(
        f'\nIf you ever need to reconfigure the cli, just run "hack configure"',
        fg="white",
    )


@cli.command()
@pass_config
@require_cli_config
def get_conf(config):
    """prints current configuration"""
    click.secho(json.dumps(get_configuration(), indent=3), fg="cyan")


@cli.command()
@pass_config
@require_cli_config
def list_accounts(config):
    """List AWS accounts designated for hackathons"""
    account_list = list_aws_accounts(config)
    click.secho(f"There are {len(account_list)} AWS accounts in the OU")
    click.secho(account_list)


@cli.command()
@pass_config
@require_cli_config
def sync(config):
    """Syncs Identity Center (IC) groups and AWS Accounts.
    Ensure one IC Group is created for each AWS account, and is assigned
    the Administrator permission set for that AWS account"""

    # Each group is granted access to this permission set in the corresponding accounts.
    PERMISSION_SET_NAME = "AWSAdministratorAccess"

    click.echo("Getting AWS account IDs from Hackathon OU...")
    # Get all AWS accounts in hackathon OU
    account_list = list_aws_accounts(config)

    click.echo(
        "Ensuring there's an IC group for each AWS Account. Creating if it's missing"
    )
    # For each AWS account, ensures there's an IC group with the same name (Account ID)
    account_id_to_group_id = sync_ic_groups(config, account_list)
    click.secho(json.dumps(account_id_to_group_id, indent=2), fg="cyan")

    # This is what the SSO Admin client needs to perform administrative tasks...
    sso_instance_arn = get_sso_instance_arn(config)

    # Get the ARN of the desired permission set.
    permission_set_arn = get_permission_set_arn(
        config, PERMISSION_SET_NAME, sso_instance_arn
    )

    # Ensures that every group has an assosciation to the admin permission set in the corresponding AWS account.
    # That mean that adding a user to an IC group, automatically grants that user admin permission to that AWS account.
    associate_group_permissions_with_aws_accounts(
        account_id_to_group_id, permission_set_arn, sso_instance_arn
    )
