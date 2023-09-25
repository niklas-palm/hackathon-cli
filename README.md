# Hackathon CLI

A small light-weight cli to manage users and account access for hackathons in AWS.

## Prerequisites.

- AWS Control Tower enabled.
- An Organizational Unit dedicated for hackathons.
- Pre-created AWS accounts in the OU.
- Identity Center set up
  - Preferably this is managed from an account that is not the Control Tower management account, but this cli will work either way

### Example usage

- Configure the CLI

```bash
hack configure
```

Persists the configuration

- Something else
