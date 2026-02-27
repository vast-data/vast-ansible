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
ansible-galaxy collection install vastdata.vms:==1.0.0
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
# Replace 1.0.0 with the desired version
ansible-galaxy collection install https://github.com/vast-data/vast-ansible/releases/download/v1.0.0/vastdata-vms-1.0.0.tar.gz
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
- **Ansible**: ansible-core >= 2.14
- **vastpy**: Python SDK for VAST (install via `pip install vastpy`)

The collection will provide a clear error message if `vastpy` is not installed.

## Quick Start

### Authentication

The collection supports two authentication methods:

#### Token-based (VAST 5.3+)

```yaml
- hosts: localhost
  tasks:
    - name: Create a view
      vastdata.vms.views:
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
        host: vast-vms.example.com
        username: admin
        password: "{{ vast_password }}"
        path: /prod/data
        state: present
```

## Available Modules

This collection provides 10 core modules for VAST storage management:

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

- **VAST Software**: 5.4.0 and later
- **Python**: 3.9+
- **Ansible**: ansible-core 2.14+

## Release Notes

See [CHANGELOG.md](CHANGELOG.md) for release history and version details.

## License

Apache License 2.0. See [LICENSE](LICENSE) for full details.

## About VAST Data

VAST Data is the data platform company for the AI era. Learn more at [vastdata.com](https://www.vastdata.com).

---

**Note**: This collection is independently developed and maintained. For VAST product documentation, visit [VAST Documentation](https://support.vastdata.com).
