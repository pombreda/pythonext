# Python Extension #

This project provides Python Mozilla bindings (PyXPCOM) that enables Python to be used inside of Mozilla applications like Firefox, Thunderbird and XULRunner.

The Python bindings are wrapped up in an extension (XPI file) so that users can easily install Pythonext just like any other Mozilla/Firefox extension.

## Compatibility ##

  * Firefox 6 (and XULRunner 6) - use pythonext version 6 from the downloads area
  * Firefox 5 (and XULRunner 5) - use pythonext version 5 from the downloads area
  * Firefox 4 (and XULRunner 2) - use pythonext version 2 from the downloads area
  * Firefox 3 and earlier - use pyxpcomext from http://pyxpcomext.mozdev.org/

  * Install the Pyshell extension from the downloads area to test that it's worked

## Why do this? ##

  * It gives the power of Python to Mozilla extension developers
  * Easy to setup multi-threaded tasks
  * Rapidly build cross platform extensions, no compilation issues!
  * Great base of core library functionality
  * Not limited to JavaScript
  * Provides a Python GUI toolkit to build applications (XULRunner)

## What does Python bring to Mozilla? ##

  * the ability to use thousands of additional python packages
  * ctypes support, easily accessing the native OS libraries
  * additional network protocol support, like SFTP, SSH access through Paramiko
  * create UDP sockets (see Mozilla [bug 191187](https://code.google.com/p/pythonext/issues/detail?id=91187))

## What are the limitations ##

  * The extension is large, between 5-15MB
  * Pythonext uses a separate extension (xpi file) for every operating system supported

## What's inside the extension? ##

  * The Python 2.6 interpreter, libraries and necessary files
  * The bindings to enable Python to communicate with Mozilla XPCOM

## How does it all work? ##

  * The Python extension is download and installed into a Mozilla application as a regular extension
  * Upon starting of the application, the extension is registered, and loads the internal dynamic linked libraries (python and pyxpcom)
  * Additional extension directories are then checked to see if there are any extensions using pyxpcom that need to be registered (and appropriately registers them)
  * The internal Python path (sys.path) is updated to reflect any "pylib" directories found in the installed extensions