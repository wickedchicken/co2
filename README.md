# co2

A service to monitor CO2 levels from a [TFA Dostmann AirCO2ntrol Mini](https://www.tfa-dostmann.de/en/produkt/co2-monitor-airco2ntrol-mini/) and notify when they've gone too high.

Based on https://hackaday.io/project/5301-reverse-engineering-a-low-cost-usb-co-monitor/log/17909-all-your-base-are-belong-to-us.

To deploy to a Debian/Ubuntu machine via Ansible, first run
`pip install -r requirements-dev.txt`. Then run

```sh
ansible-playbook -i $HOSTNAME, -u $USER -K ansible/configure-system.yml
ansible-playbook -i $HOSTNAME, -u $USER ansible/deploy.yml
```

where `$HOSTNAME` is the hostname to deploy to, and `$USER` is the user on the remote
machine. Note that you will be prompted for the `sudo` password of said user. The comma
after the hostname is necessary.

Note that the second command does not have `-K`, and therefore does not require the `sudo`
password of the user on the remote machine -- this makes it easy to repeatedly deploy code
changes without having to specify the password each time.