# Tesla T-Smart thermostat Home Assistant integration

This repository provides a custom component for enabling a [Tesla T-Smart immersion heater thermostat](https://www.teslauk.com/product/7795/t-smart-thermostat) to be used with [Home Assistant](https://home-assistant.io).

## Installation

You can install the component using either the [HACS add-on](https://hacs.xyz) or manually.

### HACS Installation

* In HACS, click the three dots, then "Custom Repositories", and add:
    * Repository = `pdw-mb/tsmart_ha`
    * Category = `integration`
* Click "Explore and download repositories", select "T-Smart thermostat", click "Download" and then restart Home Assistant

### Manual Installation

* Copy (or link) the `custom_components/t_smart/` directory from this repository into your `configuration/custom_components/` directory.

* Restart Home Assistant.

## Discover thermostats

After restarting Home Assistant:

* Go to Settings -> Devices & services -> Add Integration.

* Find "T-Smart Thermostat" and click on it.

* Click "OK" and any thermostats on your network should be discovered.



