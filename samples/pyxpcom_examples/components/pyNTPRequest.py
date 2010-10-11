#!/usr/bin/env python

#**** BEGIN LICENSE BLOCK *****
# Version: MPL 1.1/GPL 2.0/LGPL 2.1
# 
# The contents of this file are subject to the Mozilla Public License
# Version 1.1 (the "License"); you may not use this file except in
# compliance with the License. You may obtain a copy of the License at
# http://www.mozilla.org/MPL/
# 
# Software distributed under the License is distributed on an "AS IS"
# basis, WITHOUT WARRANTY OF ANY KIND, either express or implied. See the
# License for the specific language governing rights and limitations
# under the License.
# 
# The Original Code is pyxpcomext.mozdev.org code.
# 
# The Initial Developer of the Original Code is Todd Whiteman.
# Portions created by the Initial Developer are Copyright (C) 2007-2008.
# All Rights Reserved.
# 
# Contributor(s):
#   Todd Whiteman
# 
# Alternatively, the contents of this file may be used under the terms of
# either the GNU General Public License Version 2 or later (the "GPL"), or
# the GNU Lesser General Public License Version 2.1 or later (the "LGPL"),
# in which case the provisions of the GPL or the LGPL are applicable instead
# of those above. If you wish to allow use of your version of this file only
# under the terms of either the GPL or the LGPL, and not to allow others to
# use your version of this file under the terms of the MPL, indicate your
# decision by deleting the provisions above and replace them with the notice
# and other provisions required by the GPL or the LGPL. If you do not delete
# the provisions above, a recipient may use your version of this file under
# the terms of any one of the MPL, the GPL or the LGPL.
# 
#**** END LICENSE BLOCK *****

import sys
import socket
import struct
import time
import threading

from xpcom import components, ServerException, nsError
from xpcom._xpcom import getProxyForObject
try:
    # Mozilla 1.9
    from xpcom._xpcom import NS_PROXY_SYNC, NS_PROXY_ALWAYS, NS_PROXY_ASYNC
except ImportError:
    # Mozilla 1.8 used different naming for these items.
    from xpcom._xpcom import PROXY_SYNC as NS_PROXY_ASYNC
    from xpcom._xpcom import PROXY_ALWAYS as NS_PROXY_ALWAYS
    from xpcom._xpcom import PROXY_ASYNC as NS_PROXY_ASYNC

##
# This is a simple UDP time protocol request class.
# This time code is based on the ASPN Python setclock code found here:
#   http://www.nightsong.com/phr/python/setclock.py
#
#class pyNTPRequest(threading.Thread):
class pyNTPRequest:
    # XPCOM registration attributes.
    _com_interfaces_ = [components.interfaces.pyINTPRequest]
    _reg_clsid_ = "{c37c49ee-6f82-48cf-b8bf-f7e3fc34a5c5}"
    _reg_contractid_ = "@twhiteman.netfirms.com/pyNTPRequest;1"
    _reg_desc_ = "Python NTP time request"

    # time.apple.com is a stratum 2 time server.  (123 is the SNTP port number).
    # More servers info can be found at:
    #   http://www.eecis.udel.edu/~mills/ntp/servers.htm
    time_server = ('time.apple.com', 123)
    TIME1970 = 2208988800L      # Thanks to F.Lundh

    def __init__(self):
        #threading.Thread.__init__(self, name="NTP request handler")
            # setDaemon ensures the main thread will exit without having
            # to wait for this thread to die first, it just exits.
        #self.setDaemon(True)
        self._listener = None

    def asyncOpen(self, aListener):
        # We need to have a pyINTPRequestListener to send data notifications to.
        assert(aListener is not None)
        self._listener = aListener
        # Kick off the listening/processing in a thread (calls run() method).
        #self.start()
        t = threading.Thread(name="NTP request handler",
                             target=self.runAsync)
        t.setDaemon(True)
        t.start()

    def runAsync(self):
        # Important!!
        # Setup the data notification proxy. As we are running in the thread's
        # context, we *must* use a proxy when notifying the listener, otherwise
        # we end up trying to run the listener code in our thread's context
        # which will cause major problems and likely crash!
        listenerProxy = getProxyForObject(1, components.interfaces.pyINTPRequestListener,
                                          self._listener, NS_PROXY_SYNC | NS_PROXY_ALWAYS)
        listenerProxy.onStartRequest(None)

        # The sleep call is here just so the user has a chance to see the
        # listenerProxy notification updates.
        time.sleep(1)

        s = None
        context = None
        status = nsError.NS_OK
        try:
            # Setup the UDP socket and connect to the timeserver host.
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    
            data = '\x1b' + 47 * '\0'
            s.sendto(data, self.time_server)
            data, address = s.recvfrom( 1024 )
            if data:
                t = struct.unpack( '!12I', data )[10]
                if t == 0:
                    timedata = "Error processing time result."
                else:
                    timedata = time.ctime(t - self.TIME1970)
                # Turn the addr (str, num) into a list of strings.
                context = map(str, address)
                listenerProxy.onDataAvailable(context, timedata)
                context = None

            # The sleep call is here just so the user has a chance to see the
            # listenerProxy notification updates.
            time.sleep(2)

        except Exception, ex:
            context = str(ex)
            status = nsError.NS_ERROR_FAILURE
        finally:
            if s is not None:
                s.close()
            listenerProxy.onStopRequest(context, status)
            self._listener = None


# The static list of PyXPCOM classes in this module:
PYXPCOM_CLASSES = [
    pyNTPRequest,
]
