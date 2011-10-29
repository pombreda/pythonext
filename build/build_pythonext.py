from os.path import basename, join, normpath, abspath, realpath, exists, isfile, isdir, islink
import os
import sys
import traceback
import subprocess
import shutil
import glob
import time
import zipfile
import re


debug = False

XULRUNNER_SDK_VERSION = "9.0.0"

xulrunner_link_for_platform = {
        "win32":          "ftp://ftp.mozilla.org/pub/mozilla.org/xulrunner/nightly/latest-mozilla-aurora/xulrunner-9.0a2.en-US.win32.sdk.zip",
        "Darwin-x86":     "ftp://ftp.mozilla.org/pub/mozilla.org/xulrunner/nightly/latest-mozilla-aurora/xulrunner-9.0a2.en-US.mac-i386.sdk.tar.bz2",
        "Darwin-x86_64":  "ftp://ftp.mozilla.org/pub/mozilla.org/xulrunner/nightly/latest-mozilla-aurora/xulrunner-9.0a2.en-US.mac-x86_64.sdk.tar.bz2",
        "Linux-i686":     "ftp://ftp.mozilla.org/pub/mozilla.org/xulrunner/nightly/latest-mozilla-aurora/xulrunner-9.0a2.en-US.linux-i686.sdk.tar.bz2",
        "Linux-x86_64":   "ftp://ftp.mozilla.org/pub/mozilla.org/xulrunner/nightly/latest-mozilla-aurora/xulrunner-9.0a2.en-US.linux-x86_64.sdk.tar.bz2",
}

hg_cmds = [{"args": "hg clone http://hg.mozilla.org/pyxpcom -r TAG_MOZILLA_9_0_0 pyxpcom"}]

py_install_path = abspath("py_install")
py_library_path = join(py_install_path, "lib")
py_ver = "%s%s" % sys.version_info[:2]
py_ver_dotted = "%s.%s" % sys.version_info[:2]
if sys.platform == "darwin":
    py_library_path = join(py_install_path, "Python.framework", "Versions", py_ver_dotted, "lib")

patches_directory = "xulrunner-%s" % (XULRUNNER_SDK_VERSION, )


def line_strip(line):
    return line.strip().replace(" ", "").replace("\t", "").split("=")

def zip_recursively(zippath, filepaths, basepath,
                    compression=zipfile.ZIP_STORED):
    """recursively add the list of filepaths to the supplied zip file"""
    exlude_pattern_matches = map(re.compile, ["CVS", ".svn", ".hg"])
    zip = zipfile.ZipFile(zippath, "w", compression=compression)
    for filepath in filepaths:
        if isfile(filepath):
            arcname = filepath.replace(basepath, "").lstrip(r"\/")
            zip.write(filepath, arcname)
        elif isdir(filepath):
            for dirpath, dirnames, filenames in os.walk(filepath):
                dir = basename(dirpath)
                if any([exp.match(dir) for exp in exlude_pattern_matches]):
                    continue
                for filename in filenames:
                    if any([exp.match(filename) for exp in exlude_pattern_matches]):
                        continue
                    fpath = join(dirpath, filename)
                    arcname = fpath.replace(basepath, "").lstrip(r"\/")
                    if islink(fpath):
                        # Special packing of symlink in a zip file, from:
                        # http://mail.python.org/pipermail/python-list/2005-June/328433.html
                        dest = os.readlink(fpath)
                        attr = zipfile.ZipInfo()
                        attr.filename = arcname
                        attr.create_system = 3
                        attr.external_attr = 2716663808L # long type of hex val 
                                                         # of '0xA1ED0000L'
                                                         # say, symlink attr magic..
                        zip.writestr(attr, dest)
                    else:
                        zip.write(join(dirpath, filename), arcname)

def unzip_file_into_dir(filepath, dirpath):
    dirpath = os.path.abspath(dirpath)
    if not os.path.exists(dirpath):
        os.mkdir(dirpath, 0777)
    zfobj = zipfile.ZipFile(filepath)
    for name in zfobj.namelist():
        path = os.path.join(dirpath, name)
        # Check the parent directory exists - make it when it doesn't.
        parent_path = os.path.dirname(path)
        mkdir_paths = []
        while not os.path.exists(parent_path):
            mkdir_paths.append(parent_path)
            parent_path = os.path.dirname(parent_path)
        for parent_path in reversed(mkdir_paths):
            os.mkdir(parent_path, 0777)

        if path.endswith('/'):
            os.mkdir(path)
        else:
            file(path, 'wb').write(zfobj.read(name))

def trim(path):
    if exists(path):
        if isdir(path) and not islink(path):
            shutil.rmtree(path)
        else:
            os.remove(path)


class Build(object):

    def __init__(self):
        if not hasattr(self, "platform"):
            self.platform = sys.platform == "win32" and "win32" or "%s-%s" % (os.uname()[0], os.uname()[4])
        print "Building python extension\n  platform: %s\n  python version: %s" % (self.platform, sys.version.split("\n")[0])
        self._set_paths()

    def _set_paths(self, basedir=None):
        if not basedir:
            basedir = "."
        self.basedir = abspath(basedir)
        if not exists(self.basedir):
            os.mkdir(self.basedir)
        self.xulrunner_dir = join(self.basedir, "xulrunner-sdk")
        self.xulrunner_bin_dir = join(self.xulrunner_dir, "bin")
        self.pyxpcom_dir = join(self.basedir, "pyxpcom")
        self.pyxpcom_obj_dir = join(self.pyxpcom_dir, "obj_pyxpcom")
        self.build_bin_dir = join(self.pyxpcom_obj_dir, "dist", "bin")
        self.moz_xpidl = realpath(join(self.xulrunner_dir, "sdk", "bin", "xpidl.py"))
        self.moz_idl_dir = join(self.xulrunner_dir, "idl")
        self.build_lib_dir = join(self.pyxpcom_obj_dir, "dist", "lib")
        self.build_comp_dir = join(self.build_bin_dir, "components")
        self.build_python_dir = join(self.build_bin_dir, "python")

        self.pythonext_dir = join(self.basedir, "pythonext@mozdev.org")
        self.pythonext_comp_dir = join(self.pythonext_dir, "components")
        self.pythonext_lib_dir = join(self.pythonext_dir, "pylib")
        self.pythonext_python_dir = join(self.pythonext_dir, "python")

        if sys.platform.startswith("win"):
                update_target_platform = "winnt"
        elif sys.platform == "darwin":
                update_target_platform = "darwin"
        elif sys.platform.startswith("linux"):
                update_target_platform = os.uname()[4]

        self.package_conf = {
            "MOZ_APP_VERSION": "%s" % (XULRUNNER_SDK_VERSION, ),
            "TOOLKIT_MIN_VERSION": "%sa1" % (".".join(XULRUNNER_SDK_VERSION.split(".")[:2]), ),
            "TOOLKIT_MAX_VERSION": "%s.*" % (XULRUNNER_SDK_VERSION.split(".")[0], ),
            "PYTHONEXT_VERSION": "%s.%s" % (XULRUNNER_SDK_VERSION, time.strftime("%Y%m%d", time.gmtime())),
            "PYTHON_VERSION": ".".join(map(str, sys.version_info[:3])),
            "TARGET_PLATFORMS": [],
            "UPDATE_TARGET_PLATFORM": update_target_platform,
        }

        try:
            self._pre_package()
        except IOError:
            # pyxpcom not build yet - that's okay - we'll check again later.
            pass

    #---------------------------------------------------------------------------
    # building
    #---------------------------------------------------------------------------

    def xulrunner_sdk(self):
        if not exists(self.xulrunner_dir):
            import urllib2
            url = xulrunner_link_for_platform.get(self.platform)
            print "self.platform: %r, url: %r" % (self.platform, url)
            response = urllib2.urlopen(url)
            filename = join(self.basedir, "xulrunner%s" % (os.path.splitext(url)[-1]))
            try:
                file(filename, "wb").write(response.read())
                if ".zip" in filename:
                    unzip_file_into_dir(filename, ".")
                else:
                    import tarfile
                    tar = tarfile.open(filename)
                    tar.extractall(self.basedir)
            finally:
                if exists(filename):
                    os.remove(filename)

    def checkout(self):
        if not exists(self.pyxpcom_dir):
            env = os.environ.copy()
            for delete_var in ("PYTHON", "PYTHONPATH", "PYTHONHOME", "LD_LIBRARY_PATH"):
                if delete_var in env:
                    del env[delete_var]
            for cmd in hg_cmds:
                args = cmd.pop("args")
                subprocess.check_call(args.split(" "), cwd=self.basedir,
                                      env=env, **cmd)

    def patch(self):
        patches_path = abspath(join("..", "patches", patches_directory))
        for filename in glob.glob(join(patches_path, "*.patch")):
            cmd = "patch -N -p0 < %s" % filename
            subprocess.call(cmd, cwd=self.pyxpcom_dir, shell=True)

    def _add_stub(self):
        pybootstrap_path = join(self.pyxpcom_dir, "pybootstrap")
        if exists(pybootstrap_path):
            shutil.rmtree(pybootstrap_path)
        shutil.copytree(abspath(join("..", "pybootstrap")), pybootstrap_path)

        #pydom_stub_path = join(self.pyxpcom_dir, "stub_pydom")
        #if exists(pydom_stub_path):
        #    shutil.rmtree(pydom_stub_path)
        #shutil.copytree(abspath(join("..", "stub_pydom")), pydom_stub_path)

    def configure(self):
        self._pre_configure()
        self._add_stub()

    def build(self):
        autoconf_exe_name = "autoconf2.13"
        if sys.platform == "darwin":
            autoconf_exe_name = "autoconf213"
        try:
            if sys.platform.startswith("win"):
                subprocess.check_call(["sh", autoconf_exe_name],
                                      cwd=self.pyxpcom_dir)
            else:
                subprocess.check_call([autoconf_exe_name],
                                      cwd=self.pyxpcom_dir)
        except (OSError, subprocess.CalledProcessError), ex:
            if not isinstance(ex, subprocess.CalledProcessError) and \
               ex.errno != 2: # No such file or directory.
                raise
            # Try alternative naming.
            autoconf_exe_name = "autoconf-2.13"
            if sys.platform.startswith("win"):
                subprocess.check_call(["sh", autoconf_exe_name],
                                      cwd=self.pyxpcom_dir)
            else:
                subprocess.check_call([autoconf_exe_name],
                                      cwd=self.pyxpcom_dir)
        if exists(self.pyxpcom_obj_dir):
            shutil.rmtree(self.pyxpcom_obj_dir)
        os.mkdir(self.pyxpcom_obj_dir)
        argv = ["/".join(("..", "configure")), "--with-libxul-sdk=%s" % (self.xulrunner_dir)]
        if sys.platform.startswith("win"):
            argv = ["sh"] + argv
        subprocess.check_call(argv, cwd=self.pyxpcom_obj_dir)
        subprocess.check_call(["make"], cwd=self.pyxpcom_obj_dir)


    #---------------------------------------------------------------------------
    # packaging
    #---------------------------------------------------------------------------

    def _dll_name(self, name):
        return "%s%s%s" % (self.package_conf["DLL_PREFIX"], name, self.package_conf["DLL_SUFFIX"])

    def _pre_package(self, filename=None):
        filename = filename or join(self.pyxpcom_obj_dir, "config", "autoconf.mk")
        autoconf = open(filename, "r")
        os_target = None
        target_xpcom_abi = None
        self.package_conf["TARGET_PLATFORMS"] = []
        for line in autoconf:
            if not os_target and line.startswith("OS_TARGET"):
                os_target = line_strip(line)[1]
            if not target_xpcom_abi and line.startswith("TARGET_XPCOM_ABI"):
                target_xpcom_abi = line_strip(line)[1]
            if not self.package_conf.has_key("MOZ_APP_VERSION") and line.startswith("MOZ_APP_VERSION"):
                self.package_conf.update((line_strip(line),))
            if not self.package_conf.has_key("DLL_PREFIX") and line.startswith("DLL_PREFIX"):
                self.package_conf.update((line_strip(line),))
            if not self.package_conf.has_key("DLL_SUFFIX") and line.startswith("DLL_SUFFIX"):
                self.package_conf.update((line_strip(line),))
        autoconf.close()
        if not (os_target and target_xpcom_abi):
            raise Exception("could not determine target platform")
        self.package_conf["TARGET_PLATFORMS"].append("_".join((os_target, target_xpcom_abi)))
        for key in ["MOZ_APP_VERSION", "DLL_PREFIX", "DLL_SUFFIX"]:
            if not self.package_conf.has_key(key):
                raise Exception("could not detemine %s" % key)

    def _skeleton(self):
        if exists(self.pythonext_dir):
            shutil.rmtree(self.pythonext_dir)
        shutil.copytree(abspath(join("..", "pythonext_skeleton")), self.pythonext_dir)
        # Update the manifest file.
        manifest_path = join(self.pythonext_dir, "chrome.manifest")
        content = file(manifest_path, "r").read()
        for key in ["DLL_PREFIX", "DLL_SUFFIX"]:
            value = self.package_conf.get(key)
            content = content.replace("$(%s)" % key, value)
        file(manifest_path, "w").write(content)

    @property
    def _platform_alias(self):
        plat = self.package_conf["TARGET_PLATFORMS"][0]
        if len(self.package_conf["TARGET_PLATFORMS"]) > 1:
            plat = "_".join((self.package_conf["TARGET_PLATFORMS"][0].split("_")[0], "universal"))
        return plat

    def _install_rdf(self):
        self.package_conf["RDF_TARGET_PLATFORMS"] = ""
        for target in self.package_conf["TARGET_PLATFORMS"]:
            self.package_conf["RDF_TARGET_PLATFORMS"] += "\n        <em:targetPlatform>%s</em:targetPlatform>" % target
        install_rdf_path = abspath(join(self.pythonext_dir, "install.rdf"))
        content = file(install_rdf_path, "r").read()
        for key in ["PYTHONEXT_VERSION", "PYTHON_VERSION",
                    "RDF_TARGET_PLATFORMS", "MOZ_APP_VERSION",
                    "UPDATE_TARGET_PLATFORM",
                    "TOOLKIT_MIN_VERSION", "TOOLKIT_MAX_VERSION"]:
            value = self.package_conf.get(key)
            content = content.replace("$(%s)" % key, value)
        file(install_rdf_path, "w").write(content)

    def _jar(self):
        skin_dir = join(self.pythonext_dir, "skin")
        zip_recursively(join(self.pythonext_dir, "pythonext.jar"), [skin_dir], basepath=self.pythonext_dir, compression=zipfile.ZIP_STORED)
        shutil.rmtree(skin_dir)

    def _libs(self):
        if not exists(self.pythonext_comp_dir):
            os.mkdir(self.pythonext_comp_dir)
        shutil.copytree(self.build_python_dir, self.pythonext_lib_dir)
        shutil.copy(realpath(join(self.build_comp_dir, self._dll_name("pyloader"))),
                    join(self.pythonext_lib_dir, self._dll_name("pyloader")))
        shutil.copy(realpath(join(self.build_comp_dir, self._dll_name("pybootstrap"))),
                    join(self.pythonext_comp_dir, self._dll_name("pybootstrap")))

    def _python(self):
        shutil.copytree(py_install_path, self.pythonext_python_dir, symlinks=True)
        # bin/python is good to keep, for executing as a subprocess.
        #trim(join(self.pythonext_python_dir, "bin"))
        trim(join(self.pythonext_python_lib_dir, "idlelib"))
        trim(join(self.pythonext_python_lib_dir, "lib-tk"))
        trim(join(self.pythonext_python_lib_dir, "test"))
        trim(join(self.pythonext_python_lib_dir, "lib2to3", "tests"))

    def _zip_python(self, zip):
        for dirpath, dirnames, filenames in os.walk(self.pythonext_python_lib_dir):
            try:
                zip.writepy(dirpath)
            except OSError:
                pass
        zip.close()
        shutil.rmtree(self.pythonext_python_lib_dir)

    def _xpi(self):
        filename = join(self.basedir, "pythonext-%s-%s.xpi" % (self.package_conf["PYTHONEXT_VERSION"], self._platform_alias))
        zip_recursively(filename, [self.pythonext_dir], self.pythonext_dir, compression=zipfile.ZIP_DEFLATED)

    def package(self):
        self._pre_package()
        self._skeleton()
        self._install_rdf()
        self._jar()
        self._libs()
        self._python()
        self._xpi()


class WinBuild(Build):

    def _pre_configure(self):
        os.environ["PYTHON"] = join(py_install_path, "python.exe").replace("\\", "/")

    def _set_paths(self, basedir=None):
        Build._set_paths(self, basedir=basedir)
        self.pythonext_python_lib_dir = join(self.pythonext_python_dir, "Lib")

    def _libs(self):
        Build._libs(self)
        shutil.copy(realpath(join(self.build_bin_dir, self._dll_name("pyxpcom"))),
                    join(self.pythonext_lib_dir, self._dll_name("pyxpcom")))
        #shutil.copy(realpath(join(self.build_comp_dir, self._dll_name("pydom"))),
        #            join(self.pythonext_lib_dir, self._dll_name("pydom")))
        #shutil.copy(realpath(join(self.build_comp_dir, self._dll_name("pydom_stub"))),
        #            join(self.pythonext_comp_dir, self._dll_name("pydom_stub")))

    def _python(self):
        Build._python(self)
        trim(join(self.pythonext_python_dir, "Dlls", "_tkinter.pyd"))
        trim(join(self.pythonext_python_dir, "Dlls", "tcl84.dll"))
        trim(join(self.pythonext_python_dir, "Dlls", "tclpip84.dll"))
        trim(join(self.pythonext_python_dir, "Dlls", "tix84.dll"))
        trim(join(self.pythonext_python_dir, "Dlls", "tk84.dll"))
        trim(join(self.pythonext_python_dir, "Doc"))
        trim(join(self.pythonext_python_dir, "libs"))
        trim(join(self.pythonext_python_dir, "tcl"))
        trim(join(self.pythonext_python_dir, "Tools"))
        # python.exe is good to keep, for executing as a subprocess.
        #for f in glob.glob(join(self.pythonext_python_dir, "*.exe")):
        #    trim(f)
        for f in glob.glob(join(self.pythonext_python_dir, "*.txt")):
            trim(f)
        for f in glob.glob(join(self.pythonext_python_dir, "*.msi")):
            trim(f)
        self._zip_python(zipfile.PyZipFile(join(self.pythonext_python_dir, "python%s.zip" % py_ver), "w"))


class LinBuild(Build):

    def _pre_configure(self):
        os.environ["PYTHON"] = join(py_install_path, "bin", "python")
        os.environ["LD_LIBRARY_PATH"] = py_library_path

    def _set_paths(self, basedir=None):
        Build._set_paths(self, basedir=basedir)
        self.pythonext_python_lib_dir = join(self.pythonext_python_dir, "lib", "python%s" % py_ver_dotted)

    def _libs(self):
        Build._libs(self)
        shutil.copy(realpath(join(self.build_lib_dir, self._dll_name("pyxpcom"))),
                    join(self.pythonext_lib_dir, self._dll_name("pyxpcom")))
        #shutil.copy(realpath(join(self.build_comp_dir, self._dll_name("pydom"))),
        #            join(self.pythonext_lib_dir, self._dll_name("pydom")))
        #shutil.copy(realpath(join(self.build_comp_dir, self._dll_name("pydom_stub"))),
        #            join(self.pythonext_comp_dir, self._dll_name("pydom_stub")))

    def _python(self):
        Build._python(self)
        trim(join(self.pythonext_python_dir, "share"))
        self._zip_python(zipfile.PyZipFile(join(self.pythonext_python_dir, "lib", "python%s.zip" % py_ver), "w"))
        os.mkdir(self.pythonext_python_lib_dir)
        python_lib_path = join(py_library_path, "python%s" % py_ver_dotted)
        for dirpath in ("lib-dynload", "config", "plat-linux2"):
            shutil.copytree(join(python_lib_path, dirpath), join(self.pythonext_python_lib_dir, dirpath))


class MacBuild(Build):

    def _pre_configure(self):
        os.environ["PYTHON"] = join(py_install_path, "Python.framework", "Versions", py_ver_dotted, "bin", "python")
        os.environ["DYLD_LIBRARY_PATH"] = py_library_path

    def _pre_package(self):
        Build._pre_package(self, join(self.pyxpcom_obj_dir, "config", "autoconf.mk"))

    def _set_paths(self, basedir=None):
        Build._set_paths(self, basedir=basedir)
        self.pythonext_python_dir = join(self.pythonext_dir, "Frameworks")
        self.pythonext_python_lib_dir = join(self.pythonext_python_dir, "Python.framework", "Versions", py_ver_dotted, "lib", "python%s" % py_ver_dotted)

    def _update_lib(self, filename, old_library, new_library):
        import stat
        permissions = stat.S_IMODE(os.stat(filename).st_mode)
        if not permissions & stat.S_IWRITE:
            os.chmod(filename, permissions | stat.S_IWRITE)
        subprocess.check_call(["install_name_tool", "-change", old_library, new_library, filename])

    def _libs(self):
        Build._libs(self)
        #shutil.copy(realpath(join(self.build_comp_dir, self._dll_name("pydom"))),
        #            join(self.pythonext_comp_dir, self._dll_name("pydom")))
        shutil.copy(realpath(join(self.build_lib_dir, self._dll_name("pyxpcom"))),
                    join(self.pythonext_lib_dir, self._dll_name("pyxpcom")))
        python_library_reference = join(py_install_path, "Python.framework", "Versions", py_ver_dotted, "Python")
        self._update_lib(join(self.pythonext_lib_dir, self._dll_name("pyxpcom")),
                         python_library_reference,
                         "@loader_path/../Frameworks/Python.framework/Versions/%s/Python" % py_ver_dotted)
        self._update_lib(join(self.pythonext_lib_dir, self._dll_name("pyloader")),
                         python_library_reference,
                         "@loader_path/../Frameworks/Python.framework/Versions/%s/Python" % py_ver_dotted)
        self._update_lib(join(self.pythonext_lib_dir, self._dll_name("pyloader")),
                         "@executable_path/libpyxpcom.dylib",
                         "@loader_path/../pylib/libpyxpcom.dylib")
        self._update_lib(join(self.pythonext_lib_dir, "xpcom", "_xpcom.so"),
                         python_library_reference,
                         "@loader_path/../../Frameworks/Python.framework/Versions/%s/Python" % py_ver_dotted)
        self._update_lib(join(self.pythonext_lib_dir, "xpcom", "_xpcom.so"),
                         "@executable_path/libpyxpcom.dylib",
                         "@loader_path/../../pylib/libpyxpcom.dylib")
        #self._update_lib(join(self.pythonext_comp_dir, self._dll_name("pydom")),
        #                 python_library_reference,
        #                 "@loader_path/../Frameworks/Python.framework/Versions/%s/Python" % py_ver_dotted)
        #self._update_lib(join(self.pythonext_comp_dir, self._dll_name("pydom")),
        #                 "@executable_path/libpyxpcom.dylib",
        #                 "@loader_path/../pylib/libpyxpcom.dylib")

    def _python(self):
        Build._python(self)
        trim(join(self.pythonext_python_dir, "bin"))
        trim(join(self.pythonext_python_dir, "Python.framework", "Python"))
        trim(join(self.pythonext_python_dir, "Python.framework", "Resources"))
        # bin/python is good to keep, for executing as a subprocess.
        #trim(join(self.pythonext_python_dir, "Python.framework", "Versions", py_ver_dotted, "bin"))
        trim(join(self.pythonext_python_dir, "Python.framework", "Versions", py_ver_dotted, "Mac"))
        trim(join(self.pythonext_python_dir, "Python.framework", "Versions", py_ver_dotted, "Resources"))
        trim(join(self.pythonext_python_dir, "Python.framework", "Versions", py_ver_dotted, "share"))
        self._zip_python(zipfile.PyZipFile(normpath(join(self.pythonext_python_lib_dir, "..", "python%s.zip" % py_ver)), "w"))
        os.mkdir(self.pythonext_python_lib_dir)
        python_lib_path = join(py_install_path, "Python.framework", "Versions", py_ver_dotted, "lib", "python%s" % (py_ver_dotted))
        for dirpath in ("lib-dynload", "config", "plat-darwin", "plat-mac"):
            shutil.copytree(join(python_lib_path, dirpath), join(self.pythonext_python_lib_dir, dirpath))


class MacBuild_x86(MacBuild):

    platform = 'Darwin-x86'

    def _set_paths(self):
        MacBuild._set_paths(self, "x86")

    def _pre_configure(self):
        MacBuild._pre_configure(self)
        os.environ["CFLAGS"] = "-arch i386"
        os.environ["CXXFLAGS"] = "-arch i386"
        os.environ["LDFLAGS"] = "-arch i386"


class MacBuild_x86_64(MacBuild):

    platform = 'Darwin-x86_64'

    def _set_paths(self):
        MacBuild._set_paths(self, "x86_64")

    def _pre_configure(self):
        MacBuild._pre_configure(self)
        os.environ["CFLAGS"] = "-arch x86_64"
        os.environ["CXXFLAGS"] = "-arch x86_64"
        os.environ["LDFLAGS"] = "-arch x86_64"

    def _pre_package(self):
        MacBuild._pre_package(self)
        plat = self.package_conf["TARGET_PLATFORMS"][0]
        if '64' not in plat:
            plat = plat.replace('x86', 'x86_64')
            self.package_conf["TARGET_PLATFORMS"][0] = plat

class MacBuild_Universal(MacBuild):

    platform = 'Darwin-universal'

    def _install_rdf(self):
        install_rdf_path = join(self.pythonext_dir, "install.rdf")
        if exists(install_rdf_path):
            os.remove(install_rdf_path)
        shutil.copy(abspath(join("..", "pythonext_skeleton", "install.rdf")), install_rdf_path)
        MacBuild._install_rdf(self)

    def package(self, builds):
        assert(len(builds) == 2)
        build1 = builds[0]
        build2 = builds[1]

        self.package_conf["TARGET_PLATFORMS"] = [build1.package_conf["TARGET_PLATFORMS"][0],
                                                 build2.package_conf["TARGET_PLATFORMS"][0]]
        
        if exists(self.pythonext_dir):
            shutil.rmtree(self.pythonext_dir)
        shutil.copytree(build1.pythonext_dir, self.pythonext_dir)

        librelpaths = [
            join("components", "libpybootstrap.dylib"),
            join("pylib", "libpyloader.dylib"),
            join("pylib", "libpyxpcom.dylib"),
            join("pylib", "xpcom", "_xpcom.so"),
        ]
        for librelpath in librelpaths:
            lib1 = join(build1.pythonext_dir, librelpath)
            lib2 = join(build2.pythonext_dir, librelpath)
            lib3 = join(self.pythonext_dir, librelpath)
            cmd = ["lipo", "-create", lib1, lib2, "-output", lib3]
            subprocess.check_call(cmd, cwd=self.basedir)

        self._install_rdf()
        self._xpi()

def main():
    if sys.platform.startswith("win"):
        builds = [WinBuild()]
    elif sys.platform.startswith("linux"):
        builds = [LinBuild()]
    elif sys.platform.startswith("darwin"):
        builds = [MacBuild_x86_64(), MacBuild_x86()]
    else:
        sys.exit("Abort: platform '%s' not supported" % sys.platform)

    for build in builds:
    
        # download xulrunner
        build.xulrunner_sdk()
        if not exists(build.moz_xpidl):
            raise Exception("No xpidl found in the XULRunner SDK: %r" % (build.moz_xpidl, ))
    
        # checkout
        build.checkout()
    
        # patch
        build.patch()
    
        # configure
        build.configure()
    
        # build
        build.build()
    
        # package
        build.package()

    if sys.platform.startswith("darwin") and len(builds) > 1:
        MacBuild_Universal().package(builds)


if __name__ == "__main__":

    main()

