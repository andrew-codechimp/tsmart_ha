[![GitHub Release][releases-shield]][releases]
[![GitHub Activity][commits-shield]][commits]
[![Downloads][download-latest-shield]](Downloads)

# Tesla T-Smart thermostat Home Assistant integration

This integration supports Tesla T-Smart and other branded water heaters made by EUROICC.

The integration provides a climate control with preset modes, current temperature sensor, a binary sensor for the relay, and a restart button.

Error and warning binary problem sensors (on when there's a problem) with attributes for error/warning codes are also provided for diagnostic purposes.

Additional binary sensors for each error and warning are available but disabled by default.

A synchronise time button is available if you use the inbuilt schedules and the time of the device drifts, but you do not have your thermostat internet facing to time sync automatically. This is disabled by default.


This project is not endorsed by, directly affiliated with, maintained, authorized, or sponsored by Tesla UK Limited or EUROICC.

_Please :star: this repo if you find it useful_  
_If you want to show your support please_

[!["Buy Me A Coffee"](https://www.buymeacoffee.com/assets/img/custom_images/yellow_img.png)](https://www.buymeacoffee.com/codechimp)

## Installation

If you are moving from the pdw-mb HACS version you should uninstall it first and remove the repository from HACS to avoid confusion. If you see two then select the one with the description starting with new. 

⚠️ If your T-Smart thermostat is on a different network (VLAN) you must have a static IP address. It is recommended to have it static if possible anyway to avoid having to restart the integration when it changes.

### HACS

[![Open your Home Assistant instance and open a repository inside the Home Assistant Community Store.](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=andrew-codechimp&repository=tsmart_ha&category=Integration)

Restart Home Assistant

In the HA UI go to "Configuration" -> "Integrations" click "+" and search for "T-Smart Thermostat".

### Manual Installation

<details>
<summary>Show detailed instructions</summary>

Installation via HACS is recommended, but a manual setup is supported.

- Manually copy custom_components/t_smart folder from latest release to custom_components folder in your config folder.
- Restart Home Assistant.
- In the HA UI go to "Configuration" -> "Integrations" click "+" and search for "T-Smart Thermostat"
</details>

## Discover thermostats

After restarting Home Assistant:

- Go to Settings -> Devices & services -> Add Integration.

- Find "T-Smart Thermostat" and click on it.

- Click "OK" and any thermostats on the same network should be discovered, or you can manually enter their IP address if not found.  

- If your change the IP address of your thermostat the integration will try to rediscover it automatically at restart. If your thermostat is on a different network you will have to modify this in the integration by going into settings/configure.

- By default the integration takes the average of both sensors within the thermostats, this can be changed by going into settings, configuring the thermostat and choosing a different temperature mode. For vertical thermostats the High setting will match the display and the app.

## Compatible devices

This integration works with all EUROICC water heaters.

- T-Smart
- Style boiler
- Ting-Inox
- SELFA Smart Heater
- EST
- WUG MB
- DINAK
- Hottech GR Smart
- Smart Coballes
- Logitex
- Termorad Smart
- Smart Bandini

## Acknowlgements
Thanks to pdw-mb for the [original](https://github.com/pdw-mb/tsmart_ha) version of this which is no longer maintained.

<!---->

[hacs]: https://github.com/hacs/integration
[hacsbadge]: https://img.shields.io/badge/HACS-Custom-41BDF5.svg?style=for-the-badge
[download-latest-shield]: https://img.shields.io/github/downloads/andrew-codechimp/tsmart_ha/latest/total?style=for-the-badge
[commits-shield]: https://img.shields.io/github/commit-activity/y/andrew-codechimp/tsmart_ha.svg?style=for-the-badge
[commits]: https://github.com/andrew-codechimp/tsmart_ha/commits/main
[releases-shield]: https://img.shields.io/github/release/andrew-codechimp/tsmart_ha.svg?style=for-the-badge
[releases]: https://github.com/andrew-codechimp/tsmart_ha/releases
