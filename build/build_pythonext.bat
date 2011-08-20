rem run 'cmd /c build_pyext.bat' in your mozilla-build environment

@echo off

:start
set _url=http://www.python.org/ftp/python/2.6.6
set _msi=python-2.6.6.msi
if exist %_msi% goto extract

:download
echo Downloading %_url%/%_msi%...
wget %_url%/%_msi%
if %ERRORLEVEL% gtr 0 goto error

:extract
if exist %CD%\py_install\nul goto build
echo Extracting %_msi%...
md py_install
if %ERRORLEVEL% gtr 0 goto error
msiexec /qb /a %_msi% TARGETDIR=%CD%\py_install
if %ERRORLEVEL% gtr 0 goto error

:build
echo Building python extension...
%CD%\py_install\python.exe build_pythonext.py
if %ERRORLEVEL% == 0 goto end

:error
echo Error!!!

:end
set _url=
set _msi=
