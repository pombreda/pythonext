#!/bin/bash


BASEDIR=`pwd`
PLATFORM=`uname`
ARCHITECTURE=`uname -m`

PYTHONMAJOR="2"
PYTHONMINOR="7"
PYTHONRELEASE="3"
PYTHONPRERELEASE=0
PYTHONMAJORMINOR="${PYTHONMAJOR}.${PYTHONMINOR}"
PYTHONVERSION="${PYTHONMAJOR}.${PYTHONMINOR}.${PYTHONRELEASE}"

if [ ${PYTHONPRERELEASE} == 1 ]; then
    FTPPATH="http://www.python.org/ftp/python/${PYTHONMAJORMINOR}"
else
    FTPPATH="http://www.python.org/ftp/python/${PYTHONVERSION}"
fi

UNICODETYPE="ucs2"
INSTALLDIR="${BASEDIR}/py_install"


if [ ! -e "installed" ]; then
    if [ ${PLATFORM} == 'Darwin' ]; then
        # delete previous source
        rm -rf Python-${PYTHONVERSION} || exit $?
        if [ ! -e "Python-${PYTHONVERSION}.tar.bz2" ]; then
            # download
            wget ${FTPPATH}/Python-${PYTHONVERSION}.tar.bz2 || exit $?
        fi
        # extract
        tar -xjvf Python-${PYTHONVERSION}.tar.bz2 || exit $?
        cd Python-${PYTHONVERSION}
    
        # patch setup.py
        #patch -p0 < ../Python_setup.patch || exit $?
    
        # patch Mac makefile
        #patch -p0 < ../PythonMacMakefile.patch || exit $?
    
        export MACOSX_DEPLOYMENT_TARGET=10.6

        # configure
        # Build Python as a universal framework installation.
        ./configure --enable-unicode=${UNICODETYPE} --prefix=${INSTALLDIR} --enable-framework=${INSTALLDIR} --enable-universalsdk="/Developer/SDKs/MacOSX10.6.sdk" --with-universal-archs="intel"
    
        # build
        make || exit $?
    
        # install
        make install || exit $?

    else
        # For linux, we grab the already built openkomodo python build.
        # This makes it much easier... do this for Mac as well?
        if [ "${ARCHITECTURE}" == 'i686' ]; then
            ARCHITECTURE='x86'
        fi
        if [ ! -e "linux-${ARCHITECTURE}.zip" ]; then
            wget http://svn.openkomodo.com/openkomodo/checkout/openkomodo/trunk/mozilla/prebuilt/python${PYTHONMAJORMINOR}/linux-${ARCHITECTURE}.zip || exit $?
        fi
        mkdir "$INSTALLDIR"
        unzip -d "$INSTALLDIR" "./linux-${ARCHITECTURE}.zip" || exit $?
    fi

    # we're done
    cd ${BASEDIR}
    touch "installed" || exit $?

fi


# run the python build script
if [ ${PLATFORM} == "Darwin" ]; then
    export PYTHONHOME="${BASEDIR}/py_install/Python.framework/Versions/${PYTHONMAJOR}.${PYTHONMINOR}"
else
    export PYTHONHOME="${BASEDIR}/py_install"
fi
export PATH=${PYTHONHOME}/bin:$PATH
export PYTHON=${PYTHONHOME}/bin/python
export LD_LIBRARY_PATH=${PYTHONHOME}/lib
export
${PYTHON} build_pythonext.py

