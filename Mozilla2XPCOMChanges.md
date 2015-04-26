# Overview #

Mozilla 2 (Firefox 4) has changed how XPCOM registration occurs. This details how these changes affect Python XPCOM.

For complete documentation on these changes, see the MDC page here:

https://developer.mozilla.org/en/XPCOM/XPCOM_changes_in_Gecko_2.0

# Details #

For Python XPCOM component registration there is no automatic registration anymore (i.e. just because a file is inside the components directory doesn't mean it's usable). Instead, you'll need to explicitly register your Python components in the **chrome.manifest** file.

You can see the pyShell add-on for an example of this:
[chrome.manifest](http://code.google.com/p/pythonext/source/browse/samples/pyshell/chrome.manifest)

```
interfaces components/pyISomeComponent.xpt
component {9e5c9764-d445-4fef-ae24-3432f257d190} components/pySomeComponent.py
contract @mysite.com/pySomeComponent;1 {9e5c9764-d445-4fef-ae24-3432f257d190}
```

# Components #

In order to speed up Python component load times, you can define a special PYXPCOM\_CLASSES variable that lists all of the available Python XPCOM components in the file. This is optional and when not defined the loader will iterate over all top-level objects looking for Python component classes.

As an example, here is the [pyShell.py](http://code.google.com/p/pythonext/source/browse/samples/pyshell/components/pyShell.py) code for this (set at the end of the file):

# The static list of PyXPCOM classes in this module:
```
PYXPCOM_CLASSES = [
    pyShell,
]
```

# Troubleshooting #

Some interfaces have changed in Mozilla 2 - most notably the nsIVariant. If your using this interface in an IDL file, you must be sure to generate your IDL files with the xulrunner-2 xpidl tool in order to work correctly in Firefox 4.