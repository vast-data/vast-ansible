# iac-vastcluster-ansible-demo

## Requirements

ansible [core 2.13.6]

## Hosts

Edit Hosts in the `./hosts` file following the `[virtual_clusters]` example, Delete if not applicable

## Host Vars

Create a new .yml file under the host_vars dir with the same name of your newly added host in the hosts file. e.g. `example-cluster`

Follow the examples given in `example-cluster.yml`

## Secrets

Encrypted variables such as passwords or api tokens can be kept in the `secrets.yml`

Editing File: `ansible-vault edit secrets.yml`
Example passphrase: `vastdata`

## Run All Roles in Initial Playbook for a specific host

`ansible-playbook -i hosts initial.yml --ask-vault-pass --limit example-cluster`

## Run Specific Role in Initial Playbook for a  specific host

`ansible-playbook -i hosts initial.yml --ask-vault-pass --limit example-cluster --tags setup-protectionpolicies`