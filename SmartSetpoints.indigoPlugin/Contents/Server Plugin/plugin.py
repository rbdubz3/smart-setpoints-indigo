#! /usr/bin/env python
# -*- coding: utf-8 -*-
####################
# Copyright (c) 2016, Perceptive Automation, LLC. All rights reserved.
# http://www.indigodomo.com

import indigo
import time
import datetime

# Note the "indigo" module is automatically imported and made available inside
# our global name space by the host process.

################################################################################
# Globals

################################################################################
class Plugin(indigo.PluginBase):

    #-------------------------------------------------------------------------------
    def __init__(self, pluginId, pluginDisplayName, pluginVersion, pluginPrefs):
        super(Plugin, self).__init__(pluginId, pluginDisplayName, pluginVersion, pluginPrefs)

    #-------------------------------------------------------------------------------
    # Start, Stop and Config changes
    #-------------------------------------------------------------------------------
    def startup(self):
        self.debug = self.pluginPrefs.get("showDebugInfo",False)
        self.setpointAutoInterval = self.pluginPrefs.get("setpointAutoInterval",30)
        self.pauseInterval = self.pluginPrefs.get("pauseInterval",60)
        self.changeCaptureInterval = self.pluginPrefs.get("changeCaptureInterval",5)
        self.logger.debug(u"startup")
        self.logger.debug(u"showDebugInfo:{}, setpointAutoInterval:{}, pauseInterval:{}, changeCaptureInterval:{}".format(
            str(self.debug), str(self.setpointAutoInterval), str(self.pauseInterval), str(self.changeCaptureInterval)))
        self.deviceDict = dict()
        self.floatPrecision = 1
        
        indigo.devices.subscribeToChanges()
        indigo.variables.subscribeToChanges()

    #-------------------------------------------------------------------------------
    def shutdown(self):
        self.logger.debug(u"shutdown")
        self.pluginPrefs['showDebugInfo'] = self.debug
        self.pluginPrefs['setpointAutoInterval'] = self.setpointAutoInterval
        self.pluginPrefs['pauseInterval'] = self.pauseInterval
        self.pluginPrefs['changeCaptureInterval'] = self.changeCaptureInterval

    #-------------------------------------------------------------------------------
    def closedPrefsConfigUi(self, valuesDict, userCancelled):
        self.logger.debug(u"closedPrefsConfigUi")
        if not userCancelled:
            self.debug = valuesDict.get('showDebugInfo',False)
            self.setpointAutoInterval = valuesDict.get("setpointAutoInterval",30)
            self.pauseInterval = valuesDict.get("pauseInterval",60)
            self.changeCaptureInterval = valuesDict.get("changeCaptureInterval",5)
            for devId in self.deviceDict.iterkeys():
                setpointDevice = self.deviceDict[devId]
                setpointDevice.updateChangeCaptureInterval(self.changeCaptureInterval)   
            self.logger.debug(u"showDebugInfo:{}, setpointAutoInterval:{}, pauseInterval:{}, changeCaptureInterval:{}".format(
                str(self.debug), str(self.setpointAutoInterval), str(self.pauseInterval), str(self.changeCaptureInterval)))

    ########################################
    def runConcurrentThread(self):
        self.logger.debug(u"Starting concurrent thread")
        try:
            while True:
                currentDate = datetime.datetime.now()
                remainder = currentDate.minute % self.setpointAutoInterval
                if remainder == 1:
                    try:
                        # cycle through each Smart Setpoint device
                        for devId in self.deviceDict.iterkeys():
                            # call the update method with the device instance
                            setpointDevice = indigo.devices[devId]
                            lastManualUpdStr = setpointDevice.states.get('lastManualUpdate')
                            lastManualUpdate = datetime.datetime.strptime(lastManualUpdStr, '%Y-%m-%d %H:%M:%S.%f')
                            timeDelta = currentDate - lastManualUpdate
                            lastUpdMin = int(timeDelta.days * 1440 + timeDelta.seconds/60)
                            self.logger.debug(u'"{}" runConcurrentThread - smart setpoint check - PluginProps [Heat:{} Cool:{} ThermoStatId:{}]'.format(
                                setpointDevice.name, setpointDevice.pluginProps.get('SupportsHeatSetpoint'), setpointDevice.pluginProps.get('SupportsCoolSetpoint'),
                                setpointDevice.pluginProps.get('outputDevice')))
                            self.logger.debug(u'"{}" runConcurrentThread - smart setpoint check - States [lastManualUpdate ts:{} min:{}, Heat target:{} device:{}, Cool target:{} device:{}]'.format(
                                setpointDevice.name, lastManualUpdStr, str(lastUpdMin), setpointDevice.states['heatSetpoint'], setpointDevice.states['device_setpointHeat'],
                                setpointDevice.states['coolSetpoint'], setpointDevice.states['device_setpointCool'] ))         
                            if lastUpdMin > self.pauseInterval:
                                setPointConfigs = [
                                    {"configType": "heat", 
                                        "supportedProp":"SupportsHeatSetpoint", 
                                        "statesPrefix": "heatsetpoint",
                                        "curSetpointState": "heatSetpoint",
                                        "curDeviceState": "device_setpointHeat",
                                        "thermostatState": "setpointHeat"},
                                    {"configType": "cool", 
                                        "supportedProp":"SupportsCoolSetpoint", 
                                        "statesPrefix": "coolsetpoint",
                                        "curSetpointState": "coolSetpoint",
                                        "curDeviceState": "device_setpointCool",
                                        "thermostatState": "setpointCool"},
                                ]
                                for config in setPointConfigs:
                                    updatedSetpoints = False
                                    if bool(setpointDevice.pluginProps.get(config['supportedProp'])):
                                        hrSetpoints = setpointDevice.states.get(config['statesPrefix'] + getPaddedHourStr(currentDate.hour))
                                        smartTemp = getTemperatureStrFromFloat(getSmartTemperature(hrSetpoints))
                                        self.logger.debug(u'"{}" runConcurrentThread - smart setpoint check - target {}:{}'.format(setpointDevice.name, 
                                                    config['statesPrefix'], smartTemp))
                                        if setpointDevice.pluginProps.get('outputDevice', None) is not None:
                                            thermostatDev = indigo.devices[int(setpointDevice.pluginProps['outputDevice'])]
                                            curThermSetpoint = getTemperatureStrFromFloat(thermostatDev.states[config['thermostatState']])
                                            if curThermSetpoint != smartTemp:
                                                updatedSetpoints = True
                                                self.logger.info(u'"{}" - updated thermostat {} to smart {}:{}'.format(setpointDevice.name, 
                                                        thermostatDev.name, config['statesPrefix'], smartTemp))
                                                # update the last smart time - this info is used to ensure we don't collect and track this update as user-input
                                                keyValueList = []
                                                keyValueList.append({'key':'lastSmartUpdate', 'value':str(currentDate)})
                                                keyValueList.append({'key':config['curSetpointState'], 'value':str(smartTemp)})
                                                setpointDevice.updateStatesOnServer(keyValueList)
                                                if config['configType'] == 'heat':
                                                    indigo.thermostat.setHeatSetpoint(thermostatDev.id, value=getFloatFromTemperatureStr(smartTemp))
                                                else:
                                                    indigo.thermostat.setCoolSetpoint(thermostatDev.id, value=getFloatFromTemperatureStr(smartTemp))

                                        if updatedSetpoints == True:
                                            theDevice = self.deviceDict[devId]
                                            theDevice.updateSetpointDisplay()


                    except self.StopThread:
			            pass	# Optionally catch the StopThread exception and do any needed cleanup.    
                    #finally:
                    #    pass
                #else:
                #    self.logger.debug(u'Auto setpoint update every 30min. Skipping for minute:{}'.format(str(currentDate.minute)))

                self.sleep(60)

        except self.StopThread:
            pass


    #-------------------------------------------------------------------------------
    # Device Methods
    #-------------------------------------------------------------------------------
    def deviceStartComm(self, dev):
        self.logger.debug(u"deviceStartComm: {}".format(dev.name))
        if dev.configured:
            if dev.deviceTypeId == 'SmartSetpoints':
                self.deviceDict[dev.id] = SmartSetpoints(dev, self.changeCaptureInterval, self.logger)

    #-------------------------------------------------------------------------------
    def deviceStopComm(self, dev):
        self.logger.debug(u"deviceStopComm: {}".format(dev.name))
        if dev.id in self.deviceDict:
            del self.deviceDict[dev.id]

    #-------------------------------------------------------------------------------
    def didDeviceCommPropertyChangeBLAH(self, origDev, newDev):
        self.logger.debug(u"didDeviceCommPropertyChange: {}".format(newDev.name))
        if newDev.pluginId == self.pluginId and origDev.pluginProps.get('HeatSetpointDict', None) != newDev.pluginProps.get('HeatSetpointDict', None):
            self.logger.debug(u"didDeviceCommPropertyChange - new HeatSetpointDict: {}".format(newDev.pluginProps.get('HeatSetpointDict', None)))
            return False
        return indigo.PluginBase.didDeviceCommPropertyChange(self, origDev, newDev)

    #-------------------------------------------------------------------------------
    def validateDeviceConfigUi(self, valuesDict, typeId, devId):
        errorsDict = indigo.Dict()

        # validate output 
        if not valuesDict.get('outputDevice', 0):
            errorsDict['outputDevice'] = "Required"
    
        # validate SmartSetpoints
        if typeId == 'SmartSetpoints':
            if not validateTextFieldNumber(valuesDict['InitialCoolSetpoint'], numType=float, zero=False, negative=False):
                errorsDict['InitialCoolSetpoint'] = "Must be a positive float"
            if not validateTextFieldNumber(valuesDict['InitialHeatSetpoint'], numType=float, zero=False, negative=False):
                errorsDict['InitialHeatSetpoint'] = "Must be a positive float"


        if len(errorsDict) > 0:
            self.logger.debug(u"validate device config error: \n{}".format(errorsDict))
            return (False, valuesDict, errorsDict)
        return (True, valuesDict)

    def validateDeviceConfigUiBackup(self, valuesDict, typeId, devId):
        errorsDict = indigo.Dict()

        # validate input
        if valuesDict.get('inputType','dev') == 'dev':
            if valuesDict.get('inputDevice',0):
                if valuesDict.get('inputState',''):
                    testStateValue = indigo.devices[int(valuesDict['inputDevice'])].states[valuesDict['inputState']]
                    if not validateTextFieldNumber(testStateValue, numType=float, zero=True, negative=True):
                        errorsDict['inputState'] = "Must be a numerical state"
                else:
                    errorsDict['inputState'] = "Required"
            else:
                errorsDict['inputDevice'] = "Required"

        elif valuesDict.get('inputType','dev') == 'var':
            if valuesDict.get('inputVariable',0):
                testStateValue = indigo.variables[int(valuesDict['inputVariable'])].value
                if not validateTextFieldNumber(testStateValue, numType=float, zero=True, negative=True):
                    errorsDict['inputVariable'] = "Must have a numerical value"
            else:
                errorsDict['inputVariable'] = "Required"

        if not validateTextFieldNumber(valuesDict['deadband'], numType=float, zero=True, negative=False):
            errorsDict['deadband'] = "Must be a number 0 or greater"

        if not validateTextFieldNumber(valuesDict['inputDecimals'], numType=int, zero=True, negative=False):
            errorsDict['inputDecimals'] = "Must be an integer 0 or greater"

        # validate device unistat
        if typeId == 'DeviceUnistat':
            if not validateTextFieldNumber(valuesDict['dimmerControlLevel'], numType=int, zero=False, negative=False):
                errorsDict['dimmerControlLevel'] = "Must be a positive integer"


        if len(errorsDict) > 0:
            self.logger.debug(u"validate device config error: \n{}".format(errorsDict))
            return (False, valuesDict, errorsDict)
        return (True, valuesDict)


    #-------------------------------------------------------------------------------
    # Device Config callbacks
    #-------------------------------------------------------------------------------
    def getThermoDeviceList(self, filter='', valuesDict=dict(), typeId='', targetId=0):
        return [(dev.id, dev.name) for dev in indigo.devices.iter() if (dev.id != targetId and isinstance(dev, indigo.ThermostatDevice))]

    def getOutputDeviceList(self, filter='', valuesDict=dict(), typeId='', targetId=0):
        return [(dev.id, dev.name) for dev in indigo.devices.iter() if (dev.id != targetId)]


    #-------------------------------------------------------------------------------
    # Menu Methods
    #-------------------------------------------------------------------------------
    def toggleDebug(self):
        if self.debug:
            self.logger.debug(u"Debug logging disabled")
            self.debug = False
        else:
            self.debug = True
            self.logger.debug(u"Debug logging enabled")

    #-------------------------------------------------------------------------------
    # subscribed changes
    #-------------------------------------------------------------------------------
    def deviceUpdated(self, oldDev, newDev):
        if newDev.pluginId == self.pluginId:
            # device belongs to plugin
            indigo.PluginBase.deviceUpdated(self, oldDev, newDev)
            if newDev.id in self.deviceDict:
                self.deviceDict[newDev.id].selfDeviceUpdated(newDev)
        else:
            for devId, setpointDevice in self.deviceDict.items():
                setpointDevice.outputDeviceUpdated(newDev)

    #-------------------------------------------------------------------------------
    def variableUpdated(self, oldVar, newVar):
        for devId, setpointDevice in self.deviceDict.items():
            setpointDevice.outputVariableUpdated(newVar)

###############################################################################
# Classes
###############################################################################
class SmartSetpoints(object):

    #-------------------------------------------------------------------------------
    def __init__(self, instance, changeCaptureInterval, logger):
        self.logger = logger
        self.dev = instance
        self.props = instance.pluginProps
        self.changeCaptureInterval = changeCaptureInterval
        self.logger.debug(u'Device name {}, props "{}".'.format(self.name,self.props))
        if self.props != instance.pluginProps:
            self.logger.debug(u'Replacing props for device name {}'.format(self.name))
            instance.replacePluginPropsOnServer(self.props)

        self.outputType = 'device'
        if self.outputType == 'device':
            self.outputDeviceId = int(self.props['outputDevice'])
            self.outputVariableId = None
        elif self.outputType == 'variable':
            self.outputDeviceId = None
            self.outputVariableId = int(self.props['outputVariable'])
        else:
            self.logger.error(u'"{}" output init failed'.format(self.name))
            raise

        self.supportsCool = bool(self.props['SupportsCoolSetpoint'])
        self.supportsHeat = bool(self.props['SupportsHeatSetpoint'])
        self.temperatureUnits = self.props.get('temperatureUnits', 'F')

        keyValueList = []
        # Initialize the core states
        if self.supportsHeat is True:
            if self.dev.states.get('heatSetpoint', None) is None or len(self.dev.states.get('heatSetpoint')) == 0:
                setpointStr = getTemperatureStrFromFloat(self.props['InitialHeatSetpoint'])
                self.dev.states['heatSetpoint'] = setpointStr
                self.dev.states['device_setpointHeat'] = setpointStr
                keyValueList.append({'key':'heatSetpoint', 'value':setpointStr})
                keyValueList.append({'key':'device_setpointHeat', 'value':setpointStr})
                for hourIdx in range(24):
                    hrSuffix = getPaddedHourStr(hourIdx)
                    self.dev.states['heatsetpoint' + hrSuffix] = setpointStr
                    keyValueList.append({'key':'heatsetpoint' + hrSuffix, 'value':setpointStr})
        if self.supportsCool is True:
            if self.dev.states.get('coolSetpoint', None) is None or len(self.dev.states.get('coolSetpoint')) == 0:
                setpointStr = getTemperatureStrFromFloat(self.props['InitialCoolSetpoint'])
                self.dev.states['coolSetpoint'] = setpointStr
                self.dev.states['device_setpointCool'] = setpointStr
                keyValueList.append({'key':'coolSetpoint', 'value':setpointStr})
                keyValueList.append({'key':'device_setpointCool', 'value':setpointStr})
                for hourIdx in range(24):
                    hrSuffix = getPaddedHourStr(hourIdx)
                    self.dev.states['coolsetpoint' + hrSuffix] = setpointStr
                    keyValueList.append({'key':'coolsetpoint' + hrSuffix, 'value':setpointStr})
        if len(self.dev.states.get('lastManualUpdate')) == 0:
            self.dev.states['lastManualUpdate'] = str(datetime.datetime.now())
            keyValueList.append({'key':'lastManualUpdate', 'value':str(datetime.datetime.now())})
        if len(self.dev.states.get('lastSmartUpdate')) == 0:
            self.dev.states['lastSmartUpdate'] = str(datetime.datetime.now())
            keyValueList.append({'key':'lastSmartUpdate', 'value':str(datetime.datetime.now())})
        if len(keyValueList) > 0:
            self.dev.updateStatesOnServer(keyValueList)
            self.logger.debug(u'Updated states for {}, states={}'.format(self.name, self.dev.states))
        
        self.logger.debug(u'SmartSetpoints init device name {}, states={}'.format(self.name, self.dev.states))


    #-------------------------------------------------------------------------------
    def selfDeviceUpdated(self, newDev):
        self.dev = newDev
        self.logger.debug(u'"{}" selfDeviceUpdated - evaluate equipment state [H:{}, C:{}]'.format(
            self.name, self.heatSetpoint, self.coolSetpoint))

    #-------------------------------------------------------------------------------
    def outputDeviceUpdated(self, newDev):
        if newDev.id == self.outputDeviceId:
            setPointConfigs = [
                {"configType": "heat", 
                    "supportedProp":"SupportsHeatSetpoint", 
                    "statesPrefix": "heatsetpoint",
                    "curSetpointState": "heatSetpoint",
                    "curDeviceState": "device_setpointHeat",
                    "thermostatState": "setpointHeat"},
                {"configType": "cool", 
                    "supportedProp":"SupportsCoolSetpoint", 
                    "statesPrefix": "coolsetpoint",
                    "curSetpointState": "coolSetpoint",
                    "curDeviceState": "device_setpointCool",
                    "thermostatState": "setpointCool"},
            ]
            for config in setPointConfigs:
                if bool(self.props.get(config['supportedProp'])) and newDev.states.get(config['thermostatState'], None) is not None:
                    self.logger.debug(u'"{}" outputDeviceUpdated - has {} {}'.format(self.name, 
                            config['curDeviceState'], str(newDev.states[config['thermostatState']])))
                    updatedSetpoints = False
                    keyValueList = []
                    # compare new device value to old one
                    curDevSetpoint = getTemperatureStrFromFloat(self.dev.states.get(config['curDeviceState']))
                    newDevSetpoint = getTemperatureStrFromFloat(newDev.states[config['thermostatState']])
                    selfSetpoint = getTemperatureStrFromFloat(self.dev.states.get(config['curSetpointState']))
                    if curDevSetpoint != newDevSetpoint:
                        self.dev.states[config['curDeviceState']] = newDevSetpoint
                        keyValueList.append({'key':config['curDeviceState'], 'value':newDevSetpoint})

                    if selfSetpoint != newDevSetpoint:
                        currentDate = datetime.datetime.now()
                        lastSmartUpdateStr = self.dev.states['lastSmartUpdate']
                        lastSmartUpdate = datetime.datetime.strptime(lastSmartUpdateStr, '%Y-%m-%d %H:%M:%S.%f')
                        # find the number of minutes since last smart update
                        timeDelta = currentDate - lastSmartUpdate
                        diffMinutes = int(timeDelta.days * 1440 + timeDelta.seconds/60)
                        # don't collect the prefs if it came from our smart update
                        self.logger.debug(u'"{}" outputDeviceUpdated - checking update of {} from {} to {}'.format(self.name, 
                                config['curDeviceState'], selfSetpoint, newDevSetpoint))
                        self.logger.debug(u'"{}" outputDeviceUpdated - lastSmartUpdate:{} min:{}'.format(self.name, 
                                lastSmartUpdateStr, str(diffMinutes)))
                        if diffMinutes > 1:
                            hrSuffix = getPaddedHourStr(currentDate.hour)
                            currentHrSetpoint = self.dev.states[config['statesPrefix'] + hrSuffix]
                            lastUpdateStr = self.dev.states['lastManualUpdate']
                            
                            self.logger.debug(u'"{}" outputDeviceUpdated - lastUpd:{}, newUpd:{}]'.format(self.name, 
                                    lastUpdateStr, str(currentDate)))
                            newSetpointHrStr = getSmartTemperatureStrForHour(currentStr=currentHrSetpoint, newTemp=newDevSetpoint, 
                                        lastUpdateStr=lastUpdateStr, curDate=currentDate, captureInterval=self.changeCaptureInterval)
                            
                            # save the states to the device
                            updatedSetpoints = True
                            self.dev.states[config['curSetpointState']] = newDevSetpoint
                            self.dev.states['lastManualUpdate'] = str(currentDate)
                            self.dev.states[config['statesPrefix'] + hrSuffix] = newSetpointHrStr
                            
                            # update states on the server 
                            keyValueList.append({'key':config['curSetpointState'], 'value':newDevSetpoint})
                            keyValueList.append({'key':'lastManualUpdate', 'value':str(currentDate)})
                            keyValueList.append({'key':config['statesPrefix'] + hrSuffix, 'value':newSetpointHrStr})
                            
                            newSmartAvg = getTemperatureStrFromFloat(getSmartTemperature(newSetpointHrStr))
                            self.logger.info(u'"{}" - smart setpoint capture for hour:{} {}:{} NEW smartAverage:{}]'.format(self.name, 
                                hrSuffix, config['curSetpointState'], newSetpointHrStr, newSmartAvg))

                    if len(keyValueList) > 0:
                        self.dev.updateStatesOnServer(keyValueList)
                        
                    if updatedSetpoints == True:
                        self.updateSetpointDisplay()
            

                
    #-------------------------------------------------------------------------------
    def outputVariableUpdated(self, newVar):
        if newVar.id == self.outputVariableId:
            #self.temperatureInput = newVar.value
            self.logger.debug(u'"{}" outputVariableUpdated - new variable [{}]'.format(self.name, newVar))

    #-------------------------------------------------------------------------------
    def updateChangeCaptureInterval(self, changeCaptureInterval):
        self.logger.debug(u'"{}" updateChangeCaptureInterval - new value [{}]'.format(self.name, changeCaptureInterval))
        self.changeCaptureInterval = changeCaptureInterval
        
    #-------------------------------------------------------------------------------
    def getModeName(self, mode=None):
        if mode is None: mode = self.hvacOperationMode
        return self.modeNameMap.get(mode, u'Unknown')

    def updateSetpointDisplay(self):
        curHeat = self.dev.states['heatSetpoint'] 
        curCool = self.dev.states['coolSetpoint']
        imageIcon = None 
        if self.supportsCool and self.supportsHeat:
            displayValue = u'H:{:.{}f}\xb0{} / C:{:.{}f}\xb0{}'.format(float(curHeat),1,self.temperatureUnits,float(curCool),1,self.temperatureUnits)
            imageIcon = indigo.kStateImageSel.HvacAutoMode
        elif self.supportsCool:
            displayValue = u'C:{:.{}f}\xb0{}'.format(float(curCool),1,self.temperatureUnits)
            imageIcon = indigo.kStateImageSel.HvacCoolMode
        else:
            displayValue = u'H:{:.{}f}\xb0{}'.format(float(curHeat),1,self.temperatureUnits)
            imageIcon = indigo.kStateImageSel.HvacHeatMode

        self.dev.states['setpointDisplay'] = displayValue
        self.dev.updateStateOnServer('setpointDisplay', displayValue, uiValue=displayValue)
        self.dev.updateStateImageOnServer(imageIcon)

    #-------------------------------------------------------------------------------
    # properties
    #-------------------------------------------------------------------------------
    def _heatSetpointGet(self):
        if self.props['SupportsHeatSetpoint']:
            return self.dev.states['heatSetpoint']
        else:
            return 0.0
    def _heatSetpointSet(self, newVal):
        if newVal != self.heatSetpoint:
            try:
                self.dev.updateStateOnServer('heatSetpoint', float(newVal))
                self.logger.debug(u'"{}" received heatSetpoint "{}"'.format(self.name, float(newVal)))
            except ValueError:
                self.logger.error(u'"{}" received invalid input "{}" ({})'.format(self.name, newVal, type(newVal)))
    heatSetpoint = property(_heatSetpointGet,_heatSetpointSet)
    
    def _coolSetpointGet(self):
        if self.props['SupportsCoolSetpoint']:
            return self.dev.states['coolSetpoint']
        else:
            return 0.0
    def _coolSetpointSet(self, newVal):
        if newVal != self.coolSetpoint:
            try:
                self.dev.updateStateOnServer('coolSetpoint', float(newVal))
                self.logger.debug(u'"{}" received coolSetpoint "{}"'.format(self.name, float(newVal)))
            except ValueError:
                self.logger.error(u'"{}" received invalid input "{}" ({})'.format(self.name, newVal, type(newVal)))
    coolSetpoint = property(_coolSetpointGet,_coolSetpointSet)

    #-------------------------------------------------------------------------------
    @property
    def name(self):
        return self.dev.name

################################################################################
# Utilities
################################################################################
def zint(value):
    try: return int(value)
    except: return 0

def validateTextFieldNumber(rawInput, numType=float, zero=True, negative=True):
    try:
        num = numType(rawInput)
        if not zero:
            if num == 0: raise
        if not negative:
            if num < 0: raise
        return True
    except:
        return False

################################################################################
# CALCULATE SMART TEMP Utilities
################################################################################
def getSmartTemperature(temperatureStr):
    tempArray = temperatureStr.split(",")
    totalNum = 0
    tempSum = 0.0
    for curTemp in tempArray:
        if curTemp:
            totalNum = totalNum + 1
            tempSum = tempSum + float(curTemp)

    return float(round(tempSum/totalNum, 1))

def getSmartTemperatureStrForHour(currentStr, newTemp, lastUpdateStr, curDate, captureInterval):
    # Update the setpoint for this hour of day
    # compare time delta for last update
    lastUpdate = datetime.datetime.strptime(lastUpdateStr, '%Y-%m-%d %H:%M:%S.%f')
    # find the number of minutes since last thermostat update
    timeDelta = curDate - lastUpdate
    diffMinutes = int(timeDelta.days * 1440 + timeDelta.seconds/60)
    concatStr = str(newTemp) + ',' + currentStr
    tempArray = concatStr.split(",")
    totalNum = 0
    newTemperatureStr = ''
    for curTemp in tempArray:
        totalNum = totalNum + 1
        if diffMinutes < captureInterval and totalNum == 2:
            ## we just skip the last 'first' item since it was recently added
            continue
        else:
            newTemperatureStr = newTemperatureStr + curTemp  
            if totalNum < 10 and len(curTemp) > 0:
                newTemperatureStr = newTemperatureStr + ','
        if totalNum == 10:
            break
    return newTemperatureStr

def getSmartTempHourVariable(mode, hourOfDay):
    if mode == 'heat':
        varPrefix = 'heatSetpoint'
    else:
        varPrefix = 'coolSetpoint'

    if hourOfDay < 10:
        hourVariable = varPrefix + '0' + str(hourOfDay)
    else:
        hourVariable = varPrefix + str(hourOfDay)

    return hourVariable

def getPaddedHourStr(hourOfDay):
    if hourOfDay < 10:
        return '0' + str(hourOfDay)
    return str(hourOfDay)

def getTemperatureStrFromFloat(inputFloat, precision=1):
    inputStr = float(inputFloat)
    return str(round(inputStr, precision))

def getFloatFromTemperatureStr(inputStr, precision=1):
    return round(float(inputStr), precision)
