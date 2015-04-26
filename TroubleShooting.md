# Potential Pitfalls #

## PyDOM ##

PyDOM (this is Python scripts that are loaded into the XUL/HTML page, akin to JavaScript) is no longer supported.

The last version of PythonExt to support PyDOM was the Mozilla 1.9.1 (Firefox 3.5) builds, which you can still download here:
http://pyxpcomext.mozdev.org/downloads.html

## Accessing XBL from PyXPCOM ##

[XBL](https://developer.mozilla.org/en/XBL) elements (such as gBrowser - the Firefox tabbed browser element) are not accessible from PyXPCOM, as XBL properties are not exposed to XPCOM. XBL properties are only exposed to JavaScript.

You'll get an exception like:
```
AttributeError <XPCOM component '<unknown>' has no attribute 'gBrowser'
```

# Initialization Problems #

If PyXPCOM is not loading correctly, you can try enabling the mozilla log and running from the command line - check for the loading of the pythonext library files:
```
export NSPR_LOG_MODULES="all:5"
firefox
```