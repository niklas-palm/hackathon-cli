import os
import click
import json
from functools import wraps

HACK_CONFIG_PATH = "~/.hack/config"


def store_configuration(config):
    """Stores hack cli configuration"""

    os.makedirs(os.path.dirname(HACK_CONFIG_PATH), exist_ok=True)
    os.makedirs(os.path.dirname(os.path.expanduser(HACK_CONFIG_PATH)), exist_ok=True)
    with open(os.path.expanduser(HACK_CONFIG_PATH), "w") as file:
        json.dump(config, file, indent=2)


def get_configuration():
    try:
        with open(os.path.expanduser(HACK_CONFIG_PATH), "r") as file:
            data = json.load(file)
            return data
    except FileNotFoundError:
        return None
    except json.JSONDecodeError as e:
        click.secho(
            f"Something went wrong when trying to read the configuration file...",
            fg="red",
        )

        return None


# Define a simple authentication check function
def is_configured():
    # Replace this with your authentication logic
    conf = get_configuration()
    if conf:
        return True
    return False


# Decorator to ensure configuration is set
def require_cli_config(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        if is_configured():
            # User is authenticated, call the original function
            return func(*args, **kwargs)
        else:
            # User is not authenticated, handle the error or raise an exception
            click.secho(
                "It appears you haven't configured the CLI. Run 'hack configure' ",
                fg="red",
            )

    return wrapper
