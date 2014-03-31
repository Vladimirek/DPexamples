from dataplicity.client.task import Task, onsignal

from omronTcpFins import OmronPLC

class Plc2www(Task):
    """PLC data sampler"""
    def pre_startup(self):
        """Called prior to running the project"""
        # self.conf contains the data- constants from the conf
        self.sampler = self.conf.get('samplername')
        self.livecfg = self.conf.get('valgetconfig')

    @onsignal('settings_update', 'valueget')
    def on_settings_update(self, name, settings):
        """Catches the 'settings_update' signal for 'valueget'"""
        # This signal is sent on startup and whenever settings are changed by the server
        self.plcip   = settings.get(self.livecfg, 'gplcip')
        self.plcport = settings.get_integer(self.livecfg, 'gplcport', 9600)
        self.memadr  = settings.get(self.livecfg, 'gmemaddr', "A3")        
        self.log.debug("SettingValue updated: valueget {}".format(self.memadr))

    def poll(self):
        """Called on a schedule defined in dataplicity.conf"""
        
        #read data from Omron PLC:
        plc = OmronPLC( )
        plc.openFins( self.plcip, self.plcport)
        value = plc.readFloat( self.memadr)
        plc.close()
        
        self.log.debug( "SAMPLE: {}".format( value))
        self.do_sample(value)

    def do_sample(self, value):
        self.client.sample_now(self.sampler, value)