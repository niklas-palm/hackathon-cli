# Hackathon CLI

A small light-weight cli to manage users and account access for hackathons in AWS.

## Prerequisites.

- AWS Control Tower enabled.
- An Organizational Unit dedicated for hackathons.
- Pre-created AWS accounts in the hacakthon OU.
- Identity Center set up.
- Active AWS credentials in the current environment

The following commands can be executed in the Control Tower Management account. It's a best practice to create a delegated administraror for Identity Center related operations, in which case you'll credentials for that account instead.

## Example usage

Here's how to use some of the more useful commands

### Configure the CLI

```bash
hack configure
```

Persists the configuration, including region, Identity Center ID, and Organizational Unit in which AWS Hackathon Accounts exists

### List available AWS accounts

```bash
hack get-conf
```

Prints the AWS accounts in the OU designated for Hackathons

### Delete All Identy Center hackathon groups

```bash
hack delete-groups
```

Deletes All Identy Center hackathon groups associated with the hackathon AWS accounts, effectively revoking access for participants.

Run this when you

- Finish a hackathon, and want to remove all users' access
- Want to reset the permissions each group can assume in it's respective account.

> **NOTE:** This command does not revoke active sessions. Users will have continued access for the duration of the session length. The length is configurable under IAM Identity Center, Settings, Authentication, and will apply to all users in the Identity Store.

### Create IC groups, one per AWS account

```bash
hack sync-groups
```

Ensures there's one IC group assosciated with each AWS account in the hackathon OU.

Run this when you're

- setting up IC groups for the first time,
- have added more AWS accounts to the OU,
- or after you've run `hack delete-groups`

> **NOTE:** This command allows every group to assume the AWSAdministratorAccess permission set in associated AWS account. To change what permission set to associate with the group, use the `-p` flag to specify another permssion set. For more information run `hack sync-groups --help`

### Set up users

```bash
hack setup-users
```

Takes a csv (email, team number) and adds each Identity Center user to an Identity Center group for their respective team. If the Identity Center user doesn't exist, it is created. After this command, the user will be able to sign in to the SSO portal using their email and assume the associated role in the hackathon account. New users will be prompted to create a password when signing in.

Run this command when you

- want to privision Identity Center users for each Hackathon participant,
- want to add new and existing Identity Center users to the IC groups related to the hackathon,
- want to grant users access to the SSO portal and assosciated AWS account.
