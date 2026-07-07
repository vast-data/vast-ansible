# VAST Ansible Collection

Production-ready Ansible modules for VAST Data Management System (VMS). Automate VAST storage infrastructure with idempotent, declarative modules for views, policies, authentication, and networking.

[![License](https://img.shields.io/badge/License-Apache%202.0-blue.svg)](https://opensource.org/licenses/Apache-2.0)

## Installation

### From Ansible Galaxy (Recommended)

Install the latest version directly from Ansible Galaxy:

```bash
ansible-galaxy collection install vastdata.vms
```

To install a specific version:

```bash
ansible-galaxy collection install vastdata.vms:==2.0.0
```

To upgrade to the latest version:

```bash
ansible-galaxy collection install vastdata.vms --upgrade
```

### Using requirements.yml

Create a `requirements.yml` file:

```yaml
collections:
  - name: vastdata.vms
    version: ">=1.0.0"
```

Install the collection:

```bash
ansible-galaxy collection install -r requirements.yml
```

### From GitHub Releases

Download and install from a specific GitHub release:

```bash
# Replace 2.0.0 with the desired version
ansible-galaxy collection install https://github.com/vast-data/vast-ansible/releases/download/v2.0.0/vastdata-vms-2.0.0.tar.gz
```

### From Source

For development or testing from source:

```bash
git clone https://github.com/vast-data/vast-ansible.git
cd vast-ansible
ansible-galaxy collection build
ansible-galaxy collection install vastdata-vms-*.tar.gz
```

## Requirements

- **Python**: >= 3.9
- **Ansible**: ansible-core >= 2.15
- **requests**: Python HTTP library (typically already installed with ansible-core)

## Quick Start

### Authentication

The collection supports two authentication methods:

#### Token-based (VAST 5.3+)

```yaml
- hosts: localhost
  tasks:
    - name: Create a view
      vastdata.vms.views:
        vms:
          host: vast-vms.example.com
          token: "{{ vast_token }}"
        path: /prod/data
        state: present
```

#### Username and Password

```yaml
- hosts: localhost
  tasks:
    - name: Create a view
      vastdata.vms.views:
        vms:
          host: vast-vms.example.com
          username: admin
          password: "{{ vast_password }}"
        path: /prod/data
        state: present
```

## Supported Modules

This collection currently provides the following modules:

| Module | Description |
|--------|-------------|
| `vastdata.vms.views` | Manage VAST views (file system exports) |
| `vastdata.vms.viewpolicies` | Manage view policies and configurations |
| `vastdata.vms.vippools` | Manage VIP pools for network configuration |
| `vastdata.vms.quotas` | Manage storage quotas |
| `vastdata.vms.s3policies` | Manage S3 bucket policies |
| `vastdata.vms.tenants` | Manage multi-tenancy configurations |
| `vastdata.vms.groups` | Manage user groups |
| `vastdata.vms.users` | Manage user accounts |
| `vastdata.vms.ldaps` | Configure LDAP authentication |
| `vastdata.vms.dns` | Manage DNS settings |
| `vastdata.vms.eventdefinitionconfigs` | Manage event definition configurations |
| `vastdata.vms.nonlocal_group` | Manage non-local groups |
| `vastdata.vms.nonlocal_user` | Manage non-local users |
| `vastdata.vms.nativereplicationremotetargets` | Manage native replication remote targets |
| `vastdata.vms.snapshots` | Manage snapshots |
| `vastdata.vms.globalsnapstreams` | Manage global snapshot streams |
| `vastdata.vms.protectionpolicies` | Manage protection policies (with `frames`) |
| `vastdata.vms.protectedpaths` | Manage protected paths |
| `vastdata.vms.protectedpath_streams` | Manage replication streams attached to a protected path |
| `vastdata.vms.user_key` | Manage tenant-scoped user access keys |
| `vastdata.vms.activedirectory` | Manage Active Directory configurations |
| `vastdata.vms.administrator_role` | Manage administrator roles |
| `vastdata.vms.localproviders` | Manage local identity providers |
| `vastdata.vms.s3lifecyclerules` | Manage S3 lifecycle rules |
| `vastdata.vms.managers` | Manage VMS managers |
| `vastdata.vms.manager_password` | Update a manager's password |
| `vastdata.vms.manager_authorized_status` | Query a manager's authorized status |
| `vastdata.vms.qospolicies` | Manage QoS policies |
| `vastdata.vms.apitokens` | Manage API tokens |
| `vastdata.vms.apitoken_revoke` | Revoke API tokens |
| `vastdata.vms.iamroles` | Manage IAM roles |
| `vastdata.vms.iam_role_credentials` | Query IAM role credentials |
| `vastdata.vms.iamrole_revoke_access_keys` | Revoke IAM role access keys |
| `vastdata.vms.realms` | Manage realms |
| `vastdata.vms.callhomeconfigs` | Manage Call Home configurations |
| `vastdata.vms.callhomeconfig_register_cluster` | Register a cluster with Call Home |
| `vastdata.vms.callhomeconfig_send` | Trigger a Call Home send |
| `vastdata.vms.vms` | Manage VMS instances |
| `vastdata.vms.vms_configured_idps` | Query configured identity providers for a VMS |
| `vastdata.vms.vms_set_max_api_tokens` | Set the maximum number of API tokens for a VMS |
| `vastdata.vms.nonlocal_user_key` | Manage access keys for non-local users |
| `vastdata.vms.nis` | Manage NIS configuration |
| `vastdata.vms.nis_set_posix_primary` | Set a NIS provider as the POSIX primary |
| `vastdata.vms.<resource>_info` | Read-only discovery/lookup for every listable resource (e.g. `views_info`, `vippools_info`, `tenants_info`, `permissions_info`, `nics_info`) |

## Supported Roles

This collection currently provides the following roles:

| Role | Description |
|------|-------------|
| `vastdata.vms.protectedpath` | Orchestrate VAST protected paths (VIP pools, replication peers, protection policies, protected paths, and replication/standby streams) |

### Module Documentation

View detailed module documentation:

```bash
ansible-doc vastdata.vms.views
ansible-doc vastdata.vms.quotas
ansible-doc vastdata.vms.ldaps
```

### Module Features

All modules support:
- ✅ **Idempotency** - Safe to run multiple times
- ✅ **Check Mode** - Preview changes with `--check`
- ✅ **Diff Mode** - See exact changes with `--diff`
- ✅ **Error Handling** - Clear, actionable error messages
- ✅ **Ansible Vault** - Secure credential management
- ✅ **Read-only `*_info` modules** - Discover and look up resources without making changes
- ✅ **`clear_fields`** - Explicitly reset optional fields back to their empty/null state (where supported)

### Shared Connection with `module_defaults`

Every module belongs to the `vastdata.vms.all` action group, so you can declare the `vms:` connection once for a whole play instead of repeating it on every task:

```yaml
- hosts: localhost
  module_defaults:
    group/vastdata.vms.all:
      vms:
        host: vast-vms.example.com
        token: "{{ vast_token }}"
  tasks:
    - name: List VIP pools
      vastdata.vms.vippools_info:
    - name: Create a view
      vastdata.vms.views:
        path: /prod/data
        state: present
```

## Testing

### Run Tests Locally

The collection includes comprehensive test suites:

```bash
# Sanity tests (code quality, documentation)
./test.sh sanity

# Unit tests (module structure validation)
./test.sh unit

# Build collection
./test.sh build
```

### Requirements for Testing

```bash
pip install ansible-core
```

## Compatibility

- **VAST Software**: 5.4.x and 5.5.x - a single collection auto-adapts to each cluster's VMS version (manage mixed-version fleets from one install)
- **Python**: 3.9+
- **Ansible**: ansible-core 2.15+

## Release Notes

See [CHANGELOG.md](CHANGELOG.md) for release history and version details.

## License

Apache License 2.0. See [LICENSE](LICENSE) for full details.

## About VAST Data

VAST Data is the data platform company for the AI era. Learn more at [vastdata.com](https://www.vastdata.com).

---

**Note**: This collection is independently developed and maintained. For VAST product documentation, visit [VAST Documentation](https://support.vastdata.com).
