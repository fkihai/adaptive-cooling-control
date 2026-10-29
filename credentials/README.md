# credentials/

Everything in this folder except this README is gitignored. Never commit, print or paste the private key or the token.

## `ha_token.txt`

A Home Assistant long-lived access token for this project. Create it in HA > your profile > Security > Long-lived access tokens, then save the token as the only line of `ha_token.txt`. `tools/ha_client.py` reads it for each call. Revoke it in the same page if it leaks.

## `ha_ssh_key` / `ha_ssh_key.pub` / `ha_known_hosts`

A dedicated SSH key for this project, used to install packages and read `/homeassistant` on the site's Terminal & SSH add-on.

* Never use another project's key. This key belongs to this repo only.
* The address, user and port live only in `credentials/ssh_config` (gitignored, host alias `ha-lt2`). Never write them in a tracked file. SSH only works from the office network; do not expose it through the tunnel.
* The public key is registered in the add-on's `authorized_keys` option. To rotate it: create a new key, replace that line in the add-on configuration, save, and restart the add-on.
* `ha_known_hosts` pins the server's host key; `ssh_config` already points to it.
* The private key has no passphrase so scripts can use it. Keep it out of git and out of any log.

## `ssh_config`

Local file, gitignored. Create it from this template and ask the team for the real values:

```
Host ha-lt2
    HostName <HA_LAN_IP>
    User root
    Port <SSH_PORT>
    IdentityFile credentials/ha_ssh_key
    UserKnownHostsFile credentials/ha_known_hosts
    IdentitiesOnly yes
    BatchMode yes
```

The paths are relative, so run the commands from the repo root. Typical use (config root on the site is `/homeassistant`):

```bash
ssh -F credentials/ssh_config ha-lt2 'ls /homeassistant/packages'
scp -F credentials/ssh_config packages/adaptive_cooling_lt2.yaml ha-lt2:/homeassistant/packages/
```
