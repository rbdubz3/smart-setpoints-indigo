# Smart Setpoints Plugin for Indigo

This [Indigo Domotics][3] plugin is for use with Indigo Thermostat device types. The plugin collects the last 10 setpoint values for each hour of the day. On regular intervals, the plugin will update the Thermostat Setpoints to an average for the current hour of day.

### Plugin Features
* Device Types - supports devices that extend the Indigo Thermostat device type
* Smart Setpoint Tracking - Learns the preferred setpoints based on time of day, collecting values as you interact with the thermostat. Currently stores the last 10 changes made for heat/cool setpoints for each hour of the day. 
* Setpoint Automation - Automatically updates the configured thermostat with an average of these last 10 values for the current hour of the day.
* Setpoint Automation Interval - the plugin attempts to update the thermostat setpoints periodically, based on a plugin configuration interval. However, if the setpoint was recently updated manually, the setpoints will be left as-is.

### Supported Indigo Device Types

The plugin works with the Indigo Thermostat device. So far, it's been tested with the Insteon Thermostat as well as the virtual thermostat plugin 'Unistat'

[1]: https://github.com/rbdubz3/smart-setpoints-indigo/wiki
[2]: https://github.com/rbdubz3/smart-setpoints-indigo/releases
[3]: http://www.indigodomo.com