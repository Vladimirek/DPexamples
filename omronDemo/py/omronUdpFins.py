# -*- coding: utf-8 -*-
"""
Module for read plc data via UDP FINS socket
(C) Vladimir Pekar, vpek@vpek.info, 2010
"""

import logging
import socket
import re
import struct

log = logging.getLogger()

#helper functions from to string
def int2str4(k):
    return chr((k>>24) & 0xff) + chr((k>>16) & 0xff) + chr((k>>8) & 0xff) + chr((k>>0) & 0xff)

def int2str3(k):
    return chr((k>>16) & 0xff) + chr((k>>8) & 0xff) + chr((k>>0) & 0xff)

def int2str2(k):
    return chr((k>>8) & 0xff) + chr((k>>0) & 0xff)

def binstr2int(s):
    n = 0
    for i in range(0, len(s)):
        n += ord(s[i]) * ( 1<<(8*( len(s)-i-1)))
    return n

def str2intlist(s):
    return [ord(c) for c in s]

def intlist2str(l):
    s = b''.join([int2str2(e) for e in l])
    log.debug( "{0},{1}".format(l,repr(s)))
    return s
    
def str2wordlist( raw):
    if len(raw) % 2 :
        #not walid input
        return None
    declist = [ ord( raw[i]) * 256 + ord( raw[ i+1]) for i in range(0,  len(raw), 2)]
    return declist

def intListBcdData2int( wdata):
    """ String to BCD conversion : print into hex string and convert back to int """
    s = ""
    #append all data to string 
    for d in wdata:
        s = s + "{0:04x}".format(d)
    try:
        value = int(s)
    except ValueError:
        value = None
    return value

def intList2float( wdata):
    s = ""
    #danger to replace ! this reorder input word data - LSB is first string
    for v in wdata:
        s += chr(v&0xFF)
        s += chr(v>>8)
    #print repr(s)
    value =  [ None]
    if len(s)==4 :
        value = struct.unpack('f', s)
    if len(s)==8 :
        value = struct.unpack('d', s)
    return value[0]

class FinsUDPframe():
    def __init__(self, flags=None,data=None,rawFrame=None):
        FINScommandFlags=['ICF','RSV','GCT','DNA','DA1','DA2','SNA','SA1','SA2','SID','MRC','SRC',]
        FINScommandFlagsDefaults={'ICF':0x80,'GCT':0x02,}
        #object can be constructed from Flags-command(usualy to code raw frame),
        # or from raw frame-response (to decode flags)
        if not( rawFrame is None):
            self.fromRaw = True
            self.rawFrame = rawFrame
        else:
            self.fromRaw = False
            #construct rawFrame
            self.rawFrame = b''
            for flag in FINScommandFlags:
                #if specified, use from input
                if flags.has_key( flag):
                    self.rawFrame += chr( flags[ flag])
                #if not try use default value
                elif FINScommandFlagsDefaults.has_key( flag):
                    self.rawFrame += chr(FINScommandFlagsDefaults[ flag])
                #if not use zero
                else :
                    self.rawFrame += chr( 0x00)
            #append data if any
            self.rawFrame += data

    @property
    def raw(self):
        return self.rawFrame

    @property
    def disassembled(self):
        #print self.rawFrame
        asm = {}
        asm[ 'ICF'] = binstr2int( self.rawFrame[0])
        asm[ 'RSV'] = binstr2int( self.rawFrame[1])
        asm[ 'GCT'] = binstr2int( self.rawFrame[2])
        asm[ 'DNA'] = binstr2int( self.rawFrame[3])
        asm[ 'DA1'] = binstr2int( self.rawFrame[4])
        asm[ 'DA2'] = binstr2int( self.rawFrame[5])
        asm[ 'SNA'] = binstr2int( self.rawFrame[6])
        asm[ 'SA1'] = binstr2int( self.rawFrame[7])
        asm[ 'SA2'] = binstr2int( self.rawFrame[8])
        asm[ 'SID'] = binstr2int( self.rawFrame[9])
        asm[ 'MRC'] = binstr2int( self.rawFrame[10])
        asm[ 'SRC'] = binstr2int( self.rawFrame[11])
        if self.fromRaw :
            #decode from response
            asm[ 'MRES'] = binstr2int( self.rawFrame[12])
            asm[ 'SRES'] = binstr2int( self.rawFrame[13])
            asm['response'] = self.rawFrame[14:]
        else :
            asm['command'] = self.rawFrame[12:]
        return asm

    @property
    def response(self ):
        return  self.rawFrame[14:]

    def __str__(self):
        asm = self.disassembled
        strg = ''.join([ "{0}:{1} ".format(k, repr( asm[k]), ) for k in asm.keys()])
        return strg

#provide interface to code/decode omron FINS format messages for UDP transfer
class OmronFinsCommCoder:
    def __init__(self):
        self.MEMCODES = {
           #'MemType':(bit, word)
           'C':(0x30, 0xB0),
           'W':(0x31, 0xB1),
           'H':(0x32, 0xB2),
           'A':(0x33, 0xB3),
           'D':(0x02, 0x82),
        }
        self.sid = 123
        self.cmdLog =[] #command appLog.log
        
    def _decodeMemspec(self, mem):
        memSpec= re.search('(.)([0-9]*):?([0-9]*)',mem).groups()
        ( memCodeB, memCodeW) = self.MEMCODES[ memSpec[0]]
        #construct mem specification form [Mem Type][mem Adr MSB][mem Adr LSB][bit addr]
        if memSpec[2] :
            #BIT specs
            isBit = True
            memAdr = chr( memCodeB) + int2str2( int(memSpec[1])) + chr( int(memSpec[2]))
        else:
            #Word Spec
            isBit = False
            memAdr = chr( memCodeW) + int2str2( int(memSpec[1])) + chr( 0)
        return memAdr,isBit

    def encodeMemspec( self, memAdr):
        #decode memory specification [memcode,adrHi,AdrLo,bitNumber]
        memcode = ord( memAdr[0])
        bitNo =   ord( memAdr[3])
        adrNo =   ord( memAdr[1])*256 + ord( memAdr[2])
        #iterate via memcodes - search memory string representation
        for k in self.MEMCODES.keys():
            (w,b) = self.MEMCODES[ k]
            if b == memcode :
                return "{0}{1}".format( k, adrNo)
            if w == memcode :
                return "{0}{1}:{2}".format( k, adrNo, bitNo)
        #Nothing found
        return "Uknnown " + repr(memAdr)

    def _incrementSid(self):
        self.sid = (self.sid % 254) + 1 #iterate from 1..255
        #remove old items here
        while len( self.cmdLog) > 128 :
            self.cmdLog.pop()

    def _getLogItem(self, sid):
        for i in self.cmdLog:
            if i["SID"]==sid:
                return i
        return None

    def _getLogItemAndValidate(self, rawFrame):
        ff = FinsUDPframe( rawFrame=rawFrame)
        flag = ff.disassembled
        #appLog.log.debug("Validate packet: " + str(ff))
        #search SID in command log
        li = self._getLogItem( flag["SID"])
        if li is None:
            #this sid nobody expect
            return None,"decode not logged ssid"
        #check if response command is to the right send SA1 must be readed DA1
        if flag['DA1']!=li['SA1']:
            #return None,"Loopback"
            return None,"Decode loopback ?? Log:[" + str(li) + "]" + str(ff)
        #check if response command is the same as logged command
        if flag['MRC']!=li['MRC'] or flag['SRC']!=li['SRC']:
            return None,"Decode response to another command Log:[" + str(li) + "]" + str(ff)
        #check MRES, SRES
        if flag["MRES"] != 0x00 or flag["SRES"] != 0 :
            return None,"Return Error Packet: " + str(ff)  
        #all test pass
        return li,None
    
    def readMem_f(self, mem,  length ):
        (memAdr,isBit) = self._decodeMemspec(mem)
        #increment SID
        self._incrementSid()
        raw = FinsUDPframe( flags={'MRC':0x01,'SRC':0x01,'SA1':99,'SID':self.sid},
                            data = memAdr + int2str2(length))
        #append to front of command log
        logItem = {'SID':self.sid,'MRC':0x01,'SRC':0x01,'SA1':99,'mem':mem,'length':length}
        self.cmdLog.insert(0, logItem)
        #return packet data
        return raw.raw

    def readMem_d(self, rawFrame):
        (li,err) = self._getLogItemAndValidate( rawFrame)
        if err:
            log.error("Memory Read decode error " + err)
            return None,None
        ff = FinsUDPframe( rawFrame=rawFrame)
        (memAdr,isBit) = self._decodeMemspec( li["mem"])
        #decode response 
        if isBit :
            res = [ ord(v) for v in ff.response]
        else:
            res = str2wordlist( ff.response)
        return res,memAdr

    def writeMem_noresponse(self, mem, values ):
        #extend to list if calle with scalar 
        if type(values)==type([]):
            wldata = values
        else:
            wdata = [values]    
        memAdr,isBit = self._decodeMemspec(mem)
        #construct raw packet [memtype...4Byte][write_length...2Byte][data...Nbyte]
        data = memAdr + int2str2( len(wdata))
        if isBit:
            for d in wdata:
                data += chr(d)
        else:
            #WORD specs
            for d in wdata:
                data += int2str2(d)
        raw = FinsUDPframe( flags={'MRC':0x01,'SRC':0x02,'SA1':99,'ICF':0x81}, #ICF flag 0x01=NO RESPONSE
                            data = data)
        return raw.raw


class OmronUDP:
    def __init__(self):
        self.s = None
        self.finsCoder = OmronFinsCommCoder()
        
    def bindUdp(self, port=9600, host=''):
        #host = ''   # Bind to all interfaces
        self.s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.s.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        self.s.bind((host, port))
        self.s.settimeout(1.20)
        log.info( "Socket bind info:" + str(self.s.getsockname()))

    def setTimeout( self, timeout):
        self.s.settimeout( timeout)
        log.info( "Socket timout set to :" + str(timeout))

    def close(self):
        if self.s is not None:
            self.s.close()

    def recieve_one(self):
        (message, address) = self.s.recvfrom(8192)
        return message, address

    #get all what comming to socket within timeout
    def recieve_all(self):
        response=[]
        try:
            while True:
                (message, ipAddress) = self.s.recvfrom(8192)
                response.append((message, ipAddress)) 
        except socket.timeout:
            pass
        return response

    def send(self, message, ipAddress):
        #address is (host, port)
        self.s.sendto(message, ipAddress)
        
    def readMem(self, mem, length, ipAddress):
        #format message
        raw = self.finsCoder.readMem_f( mem, length)
        #send data
        #debug print FinsUDPframe(rawFrame=raw)
        self.send( raw, ipAddress)
        #recieve responses
        responses = self.recieve_all()
        #decode responses
        readData = []
        for response in responses:
            if response[0] == raw:
                # this is loopback response - pass
                continue
            (decoded,memSpec) = self.finsCoder.readMem_d( response[0])
            if (memSpec is None) or (decoded is None):
                #failed to decode (bad response from PLC, or read broadcast from another process"
                #todo ! filter out broadcast addreses from recieving! 
                log.warning( "Invalid response from {0}:{1}".format(ipAddress,response[0]))
                continue
            readData.append( (decoded, {
                "IP":response[1][0],
                "port":response[1][1],
                "memSpec":memSpec,
                "memString":self.finsCoder.encodeMemspec(memSpec),
                }))
        return readData

    def readMem_sendOnly(self, mem, length, ipAddress):
        #format message
        raw = self.finsCoder.readMem_f( mem, length)
        #send data
        self.send( raw, ipAddress)

    def readMem_readOnly(self):
        responses = self.recieve_all()
        #decode responses
        readData = []
        for response in responses:
            (decoded,memSpec) = self.finsCoder.readMem_d( response[0])
            if memSpec is None:
                #bad response or UDP loopback 
                log.warning( "{0},{1},{2}".format( repr(response),decoded,memSpec))
                continue
            #print repr(response[0])
            readData.append( (decoded, {
                "IP":response[1][0],
                "port":response[1][1],
                "memSpec":memSpec,
                "memString":self.finsCoder.encodeMemspec( memSpec),
                }))
        return readData
    
    def writeMem_noResponse( self, mem, values, ipAddress):
        #format message
        raw = self.finsCoder.writeMem_noresponse( mem, values)
        #debug print FinsUDPframe(rawFrame=raw)
        #send message
        self.send( raw, ipAddress)
        #done - no response will come (no confirmation !!!)

import time

def main( ):

    #init PLC
    log.debug("--Start--")
    plc = OmronUDP( )
    plc.bindUdp( 9600,host='192.168.100.253')

    #do it
    while 1:
        rdata = plc.readMem( "D166",2,('192.168.100.115',9600)) # xx.xx.xx.255- broadcast - work too!
        rdata.sort()
        for (d,a) in rdata:
            print a,
            if d is None:
                e = '--- Invalid response'
                print a['IP'],e
                continue
            #print repr(d)
            print "Temperature:", intList2float(d)

        print '--- sleep ---'
        time.sleep(1.0)
        print '--- wake  ---'
        break
    plc.close()

if __name__ == "__main__":
    main()
