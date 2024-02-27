# Redmine Client

Netbot includes an advanced Redmine client

## Redmine Configuration: `.env` file

`redmine.py` relies on the following environment settings:
* `REDMINE_TOKEN`: Secure Redmine API token
* `REDMINE_URL`: URL of Redmine service

## Redmine Token

TODO: create admin user as part of Redmine deployment. Not yet implemented.

Each Redmine API token is associated with a specific user, so an specific "admin" user is created for bot API access.

### Create the `admin` user

NOTE: this should be moved to the scn-redmine install process

If the `admin` user already exists and Administrator privlidges, skip this step.

An existing Redmine administrator must log into the Redmine instance to access REDMINE_URL/user to create a new user:
* Login to Redmine via REDMINE_URL
* Click **+ New User** (top right)
* Enter the follow values. Everything else can be left as is.
  * Login: `admin`
  * First name: `Admin`
  * Last name: `-`
  * Email: `root@example.com`
  * Administrator: (check the box)
  * Authentication mode: Internal
  * Password: (generate a new secure password)
  * Confirmation: (same new password)
* Click **Create**

### Get the REDMINE_TOKEN

Once the `admin` user has been created:
* Login as the admin user with the new password
* Click on "My Account" (top right, REDMINE_URL/my/account)
* In the right-hand column, look for **API access key**
* Click the related **Show** button
* Copy the revealed token to the `.env` file as `REDMINE_TOKEN`
