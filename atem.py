#!/usr/bin/env python2.7 
# -*- coding: utf-8 -*-
# vim: tabstop=8 expandtab shiftwidth=4 softtabstop=4

import socket
import struct


def dumpHex (buffer):
    s = ''
    for c in buffer:
        s += hex(ord(c)) + ' '
    print(s)


def dumpAscii (buffer):
    s = ''
    for c in buffer:
        if (ord(c)>=0x20)and(ord(c)<=0x7F):
            s+=c
        else:
            s+='.'
    print(s)


# implements communication with atem switcher
class Atem:

    # size of header data
    SIZE_OF_HEADER = 0x0c

    # packet types
    CMD_NOCOMMAND   = 0x00
    CMD_ACKREQUEST  = 0x01
    CMD_HELLOPACKET = 0x02
    CMD_RESEND      = 0x04
    CMD_UNDEFINED   = 0x08
    CMD_ACK         = 0x10

    # labels
    LABELS_VIDEOMODES = ['525i59.94NTSC', '625i50PAL', '525i59.94NTSC16:9', '625i50PAL16:9',
                         '720p50', '720p59.94', '1080i50', '1080i59.94',
                         '1080p23.98', '1080p24', '1080p25', '1080p29.97', '1080p50', '1080p59.94',
                         '2160p23.98', '2160p24', '2160p25', '2160p29.97']
    LABELS_PORTS_EXTERNAL = ['SDI', 'HDMI', 'Component', 'Composite', 'SVideo']
    LABELS_PORTS_INTERNAL = ['External', 'Black', 'Color Bars', 'Color Generator', 'Media Player Fill',
                             'Media Player Key', 'SuperSource']
    LABELS_MULTIVIEWER_LAYOUT = ['Top', 'Bottom', 'Left', 'Right']

    system_config = { 'inputs': {} }
    status = {}
    config = { 'multiviewers': {} }
    state = {
        'program': {},
        'preview': {},
        'keyers': {},
        'dskeyers': {},
        'aux': {}
    }
    cameracontrol = {
        'features': {},
        'state': {}
    }

    # initializes the class
    def __init__(self, address):
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.socket.setblocking(0)
        self.socket.bind(('0.0.0.0', 9910))

        self.address = (address, 9910)
        self.packetCounter = 0
        self.isInitialized = False
        self.currentUid = 0x1337

        self.LABELS_PORTS_INTERNAL[128] = 'ME Output'
        self.LABELS_PORTS_INTERNAL[129] = 'Auxilary'
        self.LABELS_PORTS_INTERNAL[130] = 'Mask'

    # hello packet
    def connectToSwitcher(self):
        datagram = self.createCommandHeader(self.CMD_HELLOPACKET, 8, self.currentUid, 0x0)
        datagram += struct.pack('!I', 0x01000000)
        datagram += struct.pack('!I', 0x00)
        self.sendDatagram(datagram)

    # reads packets sent by the switcher
    def handleSocketData (self) :
        # network is 100Mbit/s max, MTU is thus at most 1500
        try :
            d = self.socket.recvfrom(2048)
        except socket.error:
            return False
        datagram, server = d
        print('received datagram')
        header = self.parseCommandHeader(datagram)
        if header :
            self.currentUid = header['uid']
            
            if header['bitmask'] & self.CMD_HELLOPACKET :
                print('not initialized, received HELLOPACKET, sending ACK packet')
                self.isInitialized = False
                ackDatagram = self.createCommandHeader (self.CMD_ACK, 0, header['uid'], 0x0)
                self.sendDatagram (ackDatagram)
            elif self.isInitialized and (header['bitmask'] & self.CMD_ACKREQUEST) :
                print('initialized, received ACKREQUEST, sending ACK packet')
                ackDatagram = self.createCommandHeader (self.CMD_ACK, 0, header['uid'], header['packageId'])
                self.sendDatagram (ackDatagram)
            
            if len(datagram) > self.SIZE_OF_HEADER + 2 and not (header['bitmask'] & self.CMD_HELLOPACKET) :
                self.parsePayload (datagram)

        return True        

    def waitForPacket(self):
        print(">>> waiting for packet")
        while not self.handleSocketData():
            pass
        print(">>> packet obtained")

    # generates packet header data
    def createCommandHeader (self, bitmask, payloadSize, uid, ackId) :
        buffer = ''
        packageId = 0

        if not (bitmask & (self.CMD_HELLOPACKET | self.CMD_ACK)) :
            self.packetCounter+=1
            packageId = self.packetCounter
    
        val = bitmask << 11
        val |= (payloadSize + self.SIZE_OF_HEADER)
        buffer += struct.pack('!H',val)
        buffer += struct.pack('!H',uid)
        buffer += struct.pack('!H',ackId)
        buffer += struct.pack('!I',0)
        buffer += struct.pack('!H',packageId)
        return buffer

    # parses the packet header
    def parseCommandHeader (self, datagram) :
        header = {}

        if len(datagram)>=self.SIZE_OF_HEADER :
            header['bitmask'] = struct.unpack('B',datagram[0])[0] >> 3
            header['size'] = struct.unpack('!H',datagram[0:2])[0] & 0x07FF
            header['uid'] = struct.unpack('!H',datagram[2:4])[0]
            header['ackId'] = struct.unpack('!H',datagram[4:6])[0]
            header['packageId']=struct.unpack('!H',datagram[10:12])[0]
            print(header)
            return header
        return False

    def parsePayload (self, datagram) :
        print('parsing payload')
        # eat up header
        datagram = datagram[self.SIZE_OF_HEADER:]
        # handle data
        while len(datagram) > 0 :
            size = struct.unpack('!H',datagram[0:2])[0]
            packet = datagram[0:size]
            datagram = datagram[size:]

            # skip size and 2 unknown bytes
            packet = packet[4:]
            ptype = packet[:4]
            payload = packet[4:]

            # find the approporiate function in the class
            method = 'recv'+ptype
            if method in dir(self) :
                func = getattr(self, method)
                if callable(func) :
                    print(method)
                    func(payload)
                else:
                    print('problem, member '+method+' not callable')
            else :
                print('unknown type '+ptype)
                #dumpAscii(payload)

        #sys.exit()

    def sendCommand (self, command, payload) :
        print('sending command')
        size = len(command) + len(payload) + 4
        dg = self.createCommandHeader(self.CMD_ACKREQUEST, size, self.currentUid, 0)
        dg += struct.pack('!H', size)
        dg += "\x00\x00"
        dg += command
        dg += payload
        self.sendDatagram(dg)

    # sends a datagram to the switcher
    def sendDatagram (self, datagram) :
        print('sending packet')
        dumpHex(datagram)
        self.socket.sendto (datagram, self.address)

    def parseBitmask(self, num, labels):
        states = {}
        for i, label in enumerate(labels):
            states[label] = bool(num & (1 << len(labels) - i - 1))
        return states


    # handling of subpackets
    # ----------------------

    def recv_ver(self, data):
        major, minor = struct.unpack('!HH', data)
        self.system_config['version'] = str(major)+'.'+str(minor)

    def recv_pin (self, data):
        self.system_config['name'] = data

    def recvWarn(self, text):
        print('Warning: '+text)

    def recv_top(self, data):
        self.system_config['topology'] = {}
        datalabels = ['mes', 'sources', 'color_generators', 'aux_busses', 'dsks', 'stingers', 'dves',
                      'supersources']
        for i, label in enumerate(datalabels):
            self.system_config['topology'][label] = data[i]

        self.system_config['topology']['hasSD'] = (data[9] > 0)

    def recv_MeC(self, data):
        if not 'keyers' in self.system_config:
            self.system_config['keyers'] = {}
        index = data[0]
        self.system_config['keyers'][index] = data[1]

    def recv_mpl(self, data):
        self.system_config['media_players'] = {}
        self.system_config['media_players']['still'] = data[0]
        self.system_config['media_players']['clip'] = data[1]

    def recv_MvC(self, data):
        self.system_config['multiviewers'] = data[0]

    def recv_SSC(self, data):
        self.system_config['super_source_boxes'] = data[0]

    def recv_TlC(self, data):
        self.system_config['tally_channels'] = data[4]

    def recv_AMC(self, data):
        self.system_config['audio_channels'] = data[0]
        self.system_config['has_monitor'] = (data[1] > 0)

    def recv_VMC(self, data):
        size = 18
        for i in range(size):
            self.system_config['video_modes'][i] = bool(data[0] & (1 << size - i - 1))

    def recv_MAC(self, data):
        self.system_config['macro_banks'] = data[0]

    def recvPowr(self, data):
        self.status['power'] = self.parseBitmask(data[0], ['main', 'backup'])

    def recvDcOt(self, data):
        self.config['down_converter'] = data[0]

    def recvVidM(self, data):
        self.config['video_mode'] = data[0]

    def recvInPr(self, data):
        index = struct.unpack('!H', data[0:2])
        self.system_config['inputs'][index] = {}
        with self.system_config['inputs'][index] as input:
            input['name_long'] = data[2:21]
            input['name_short'] = data[22:25]
            input['types_available'] = self.parseBitmask(data[27], self.LABELS_PORTS_EXTERNAL)
            input['port_type_external'] = data[29]
            input['port_type_internal'] = data[30]
            input['availability'] = self.parseBitmask(data[32], ['Auxilary', 'Multiviewer', 'SuperSourceArt',
                                                                 'SuperSourceBox', 'KeySource'])
            input['me_availability'] = self.parseBitmask(data[33], ['ME1', 'ME2'])

    def recvMvPr(self, data):
        index = data[0]
        if index not in self.config['multiviewers']:
            self.config['multiviewers'][index] = {}
        self.config['multiviewers'][index]['layout'] = data[1]

    def recvMvIn(self, data):
        index = data[0]
        if index not in self.config['multiviewers']:
            self.config['multiviewers'][index] = {}
        if 'windows' not in self.config['multiviewers'][index]:
            self.config['multiviewers'][index]['windows'] = {}
        window = data[1]
        self.config['multiviewers'][index]['windows'][window] = struct.unpack('!H', data[2:3])

    def recvPrgI(self, data):
        meIndex = data[0]
        self.state['program'][meIndex] = struct.unpack('!H', data[2:3])

    def recvPrvI(self, data):
        meIndex = data[0]
        self.state['preview'][meIndex] = struct.unpack('!H', data[2:3])

    def recvKeOn(self, data):
        meIndex = data[0]
        keyer = data[1]
        if meIndex not in self.state['keyers']:
            self.state['keyers'][meIndex] = {}
        self.state['keyers'][meIndex][keyer] = (data[2] != 0)

    def recvDskB(self, data):
        keyer = data[0]
        if keyer not in self.state['dskeyers']:
            self.state['dskeyers'][keyer] = {}
        self.state['dskeyers'][keyer]['fill'] = struct.unpack('!H', data[2:3])
        self.state['dskeyers'][keyer]['key'] = struct.unpack('!H', data[4:5])

    def recvDskS(self, data):
        keyer = data[0]
        if keyer not in self.state['dskeyers']:
            self.state['dskeyers'][keyer] = {}
        self.state['dskeyers'][keyer]['onAir'] = (data[1] != 0)
        self.state['dskeyers'][keyer]['inTransition'] = (data[2] != 0)
        self.state['dskeyers'][keyer]['autoTransitioning'] = (data[3] != 0)
        self.state['dskeyers'][keyer]['framesRemaining'] = data[4]

    def recvAuxS(self, data):
        auxIndex = data[0]
        self.state[auxIndex] = struct.unpack('!H', data[2:3])

    def recvCCdo(self, data):
        input = data[1]
        domain = data[2]
        feature = data[3]


if __name__ == '__main__':
    import config
    a = Atem(config.address)
    a.connectToSwitcher()
    #while (True):
    import time
    a.waitForPacket()
    a.waitForPacket()
    a.waitForPacket()
    a.waitForPacket()
    a.waitForPacket()
    a.waitForPacket()
    a.waitForPacket()
    print("sending command")
    a.sendCommand("DCut", "\x00\x00\x00\x00")
    a.waitForPacket()    
