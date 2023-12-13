# vast-ansible

## Requirements

Ansible https://github.com/ansible/ansible
Yaml Editor such as VS Code https://code.visualstudio.com/


## Hosts

Edit Hosts in the `./hosts` file following the `[virtual_clusters]` example, Delete if not applicable


## Host Vars

Create a new .yml file under the host_vars dir with the same name of your newly added host in the hosts file. e.g. `example-cluster`

Follow the examples given in `example-cluster.yml`


## Secrets

Encrypted variables such as passwords or api tokens can be kept in the `secrets.yml`

Editing File: `ansible-vault edit secrets.yml`

Default passphrase: `vastdata`


## Run All Roles in Initial Playbook for a specific host

`ansible-playbook -i hosts initial.yml --ask-vault-pass --limit example`


## Run Specific Role in Initial Playbook for a specific host

`ansible-playbook -i hosts initial.yml --ask-vault-pass --limit example --tags setup-protectionpolicies`

## WIP Roles
Native Replication
Failover