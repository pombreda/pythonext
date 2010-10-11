Python Extension (PythonExt) README
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Introduction
============

This provides instructions for setting up and building the PyXPCOM
extension from source.

Layout:
    build/                - scripts for creating pythonext.
    patches/              - specific pyxpcom/pydom patches that need be applied
    pybootstrap/          - sets up python and then pyxpcom libraries.
    pythonext_skeletion/  - framework for the pythonext extension.
    samples/              - examples using python in a mozilla extension.
    stub_pydom/           - loads the pydom component and necessary libraries.


How the extension works
=======================

The pybootstrap directory is copied into the mozilla/extensions directory and
the mozilla build is configured to compile this stub extension. The bootstrap is
responsible for loading the correct (internal) python library that will be
used by pyxpcom and pydom. The pybootstrap module will load the modified
pyxpcom loader component and then trigger the normal pyxpcom registration
process.

A pyxpcom registration helper is used "pyIXPCOMExtensionHelper.idl" to ensure
that *all* installed python xpcom extensions get registered and that the
python path is adjusted correctly for any of these extensions.

An extension that wants to add it's own python library code will need to
package the code into a pylib subdirectory of the extension xpi, this pylib
directory will automatically get added to sys.path at application startup.


Build process
=============

The Mozilla build requirements must already be met.

Mac OS X and Linux
------------------

Change to the build directory and then execute the build script:
$ ./build_pythonext.sh

If the build is successful, you will find an extension (xpi) file in the build
directory that can be installed into a Mozilla based application.


Windows
-------

In addition to the mozilla build requirements, you will also need to have the
"wget" executable available on your PATH.

Change to the build directory and then execute the build script:
$ ./build_pythonext.bat

If the build is successful, you will find an extension (xpi) file in the build
directory that can be installed into a Mozilla based application.


History
=======
This extension was previously called pyxpcomext when it was only using the
Python XPCOM bridging, but now that the extension also includes the Python
DOM handling code it was renamed to pythonext.


Contributors
============
* lekma - reworked the builds scripts and the pybootstrap code.
* Simon Kornblith - patches to pybootstrap and build scripts.

