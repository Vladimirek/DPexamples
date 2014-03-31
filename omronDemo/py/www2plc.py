from dataplicity.client.task import Task, onsignal

from omronTcpFins import OmronPLC

class Www2plc(Task):
    """PLC data writer"""
    def pre_startup(self):
        """Called prior to running the project"""
        # self.conf contains the data- constants from the conf
        self.livecfg = self.conf.get('valsetconfig')

    @onsignal('settings_update', 'valueset')
    def on_settings_update(self, name, settings):
        """Catches the 'settings_update' signal for 'valueset'"""
        # This signal is sent on startup and whenever settings are changed by the server
        self.plcip   = settings.get(self.livecfg, 'splcip')
        self.plcport = settings.get_integer(self.livecfg, 'splcport', 9600)
        self.memadr  = settings.get(self.livecfg, 'smemaddr', "A0")        
        self.savevalue = settings.get_float(self.livecfg, 'savevalue', 0.0)
        self.log.debug(" SettingValue updated: valueset {}:{}".format(self.memadr, self.savevalue))
        
        #write data to Omron PLC:
        plc = OmronPLC( )
        plc.openFins( self.plcip, self.plcport)
        plc.writeFloat( self.memadr, self.savevalue)
        plc.close()

    def poll(self):
        """Called on a schedule defined in dataplicity.conf"""
        pass #nothing to do regullary
