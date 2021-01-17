# Smart Setpoints Plugin for Indigo

This [Indigo Domotics][3] plugin is for use with Indigo Thermostat device types. The plugin collects the last 10 setpoint values for each hour of the day. On regular intervals, the plugin will update the Thermostat setpoints to an average.

### Plugin Features
* Device Types - supports devices that extend the Indigo Thermostat device 
* Smart Setpoints - stores the last 10 changes made to the setpoints. Automatically updates the configured thermostat with an average of these last 10 values
* Auto Update Interval - the plugin attempts to update the thermostat every 30 minutes. However, if the thermostat setpoint was updated manually within the last hour, the setpoints will be left as-is.

### Supported Indigo Device Types

The plugin works with the Indigo Thermostat device. So far, it's been tested with the Insteon Thermostat as well as the virtual thermostat plugin 'Unistat'

[1]: https://github.com/rbdubz3/sylvania-lightify-indigo/wiki
[2]: https://github.com/rbdubz3/sylvania-lightify-indigo/releases
[3]: http://www.indigodomo.com