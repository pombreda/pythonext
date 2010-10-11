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

xulrunner_link_for_platform = {
        "win32":          "http://ftp.mozilla.org/pub/mozilla.org/xulrunner/nightly/latest-mozilla-central/xulrunner-2.0b8pre.en-US.win32.sdk.zip",
        "Darwin-i386":    "http://ftp.mozilla.org/pub/mozilla.org/xulrunner/nightly/latest-mozilla-central/xulrunner-2.0b7pre.en-US.mac-i386.sdk.tar.bz2",
        "Linux-i686":     "http://ftp.mozilla.org/pub/mozilla.org/xulrunner/nightly/latest-mozilla-central/xulrunner-2.0b8pre.en-US.linux-i686.sdk.tar.bz2",
        "Linux-x86_64":   "http://ftp.mozilla.org/pub/mozilla.org/xulrunner/nightly/latest-mozilla-central/xulrunner-2.0b8pre.en-US.linux-x86_64.sdk.tar.bz2",
}

hg_cmds = [{"args": "hg clone http://hg.mozilla.org/pyxpcom pyxpcom"}]

py_install_path = abspath("py_install")
py_library_path = join(py_install_path, "lib")
py_ver = "%s%s" % sys.version_info[:2]
py_ver_dotted = "%s.%s" % sys.version_info[:2]
if sys.platform == "darwin":
    py_library_path = join(py_install_path, "Python.framework", "Versions", py_ver_dotted, "lib")

moz_ver_string = "mozilla2.0.0"

pyxpcom_obj_dir = abspath(join("pyxpcom", "obj_pyxpcom"))

pythonext_dir = abspath("pythonext@mozdev.org")
pythonext_comp_dir = join(pythonext_dir, "components")
pythonext_lib_dir = join(pythonext_dir, "pylib")

package_conf = {
    "PYTHONEXT_VERSION": "%s.%s" % (".".join(map(str, sys.version_info[:3])),
                                    time.strftime("%Y%m%d", time.gmtime())),
    "PYTHON_VERSION": ".".join(map(str, sys.version_info[:3])),
    "TARGET_PLATFORMS": [],
    "MOZ_APP_VERSION": "2.0.0",
}


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

def trim(path):
    if exists(path):
        if isdir(path) and not islink(path):
            shutil.rmtree(path)
        else:
            os.remove(path)


class Build(object):

    def __init__(self):
        print "Building python extension\nplatform: %s\nversion: %s" % (sys.platform, sys.version.split("\n")[0])


    #---------------------------------------------------------------------------
    # building
    #---------------------------------------------------------------------------

    def xulrunner_sdk(self):
        if not exists("xulrunner-sdk"):
            import urllib2
            platform = sys.platform == "win32" and "win32" or "%s-%s" % (os.uname()[0], os.uname()[4])
            url = xulrunner_link_for_platform.get(platform)
            response = urllib2.urlopen(url)
            filename = "xulrunner%s" % (os.path.splitext(url)[-1])
            try:
                file(filename, "wb").write(response.read())
                import tarfile
                tar = tarfile.open(filename)
                tar.extractall()
            finally:
                if exists(filename):
                    os.remove(filename)

    def checkout(self):
        if not exists("pyxpcom"):
            env = os.environ.copy()
            for delete_var in ("PYTHON", "PYTHONPATH", "PYTHONHOME", "LD_LIBRARY_PATH"):
                if delete_var in env:
                    del env[delete_var]
            for cmd in hg_cmds:
                args = cmd.pop("args")
                subprocess.check_call(args.split(" "), env=env, **cmd)

    def patch(self):
        patches_path = abspath(join("..", "patches", moz_ver_string))
        for filename in glob.glob(join(patches_path, "*.patch")):
            cmd = "patch -N -p0 -i %s" % filename
            subprocess.call(cmd, cwd=abspath("pyxpcom"), shell=True)

    def _add_stub(self):
        pybootstrap_path = abspath(join("pyxpcom", "pybootstrap"))
        if exists(pybootstrap_path):
            shutil.rmtree(pybootstrap_path)
        shutil.copytree(abspath(join("..", "pybootstrap")), pybootstrap_path)

        pydom_stub_path = abspath(join("pyxpcom", "stub_pydom"))
        if exists(pydom_stub_path):
            shutil.rmtree(pydom_stub_path)
        shutil.copytree(abspath(join("..", "stub_pydom")), pydom_stub_path)

    def configure(self):
        self._pre_configure()
        self._add_stub()

    def build(self):
        autoconf_exe_name = "autoconf2.13"
        if sys.platform == "darwin":
            autoconf_exe_name = "autoconf213"
        try:
            subprocess.check_call([autoconf_exe_name], cwd=abspath("pyxpcom"))
        except OSError, ex:
            if ex.errno == 2: # No such file or directory.
                # Try alternative naming.
                subprocess.check_call(["autoconf-2.13"], cwd=abspath("pyxpcom"))
            else:
                raise
        if exists(pyxpcom_obj_dir):
            shutil.rmtree(pyxpcom_obj_dir)
        os.mkdir(pyxpcom_obj_dir)
        subprocess.check_call([join("..", "configure"), "--with-libxul-sdk=%s" % (abspath("xulrunner-sdk"))], cwd=pyxpcom_obj_dir)
        subprocess.check_call(["make"], cwd=pyxpcom_obj_dir)


    #---------------------------------------------------------------------------
    # packaging
    #---------------------------------------------------------------------------

    def _dll_name(self, name):
        return "%s%s%s" % (package_conf["DLL_PREFIX"], name, package_conf["DLL_SUFFIX"])

    def _pre_package(self, filename=None):
        filename = filename or join(pyxpcom_obj_dir, "config", "autoconf.mk")
        autoconf = open(filename, "r")
        os_target = None
        target_xpcom_abi = None
        for line in autoconf:
            if not os_target and line.startswith("OS_TARGET"):
                os_target = line_strip(line)[1]
            if not target_xpcom_abi and line.startswith("TARGET_XPCOM_ABI"):
                target_xpcom_abi = line_strip(line)[1]
            if not package_conf.has_key("MOZ_APP_VERSION") and line.startswith("MOZ_APP_VERSION"):
                package_conf.update((line_strip(line),))
            if not package_conf.has_key("DLL_PREFIX") and line.startswith("DLL_PREFIX"):
                package_conf.update((line_strip(line),))
            if not package_conf.has_key("DLL_SUFFIX") and line.startswith("DLL_SUFFIX"):
                package_conf.update((line_strip(line),))
        autoconf.close()
        if not (os_target and target_xpcom_abi):
            raise Exception("could not determine target platform")
        package_conf["TARGET_PLATFORMS"].append("_".join((os_target, target_xpcom_abi)))
        for key in ["MOZ_APP_VERSION", "DLL_PREFIX", "DLL_SUFFIX"]:
            if not package_conf.has_key(key):
                raise Exception("could not detemine %s" % key)

    def _skeleton(self):
        if exists(pythonext_dir):
            shutil.rmtree(pythonext_dir)
        shutil.copytree(abspath(join("..", "pythonext_skeleton")), pythonext_dir)

    @property
    def _platform_alias(self):
        plat = package_conf["TARGET_PLATFORMS"][0]
        if len(package_conf["TARGET_PLATFORMS"]) > 1:
            plat = "_".join((package_conf["TARGET_PLATFORMS"][0].split("_")[0], "universal"))
        return plat

    def _install_rdf(self):
        package_conf["RDF_TARGET_PLATFORMS"] = ""
        for target in package_conf["TARGET_PLATFORMS"]:
            package_conf["RDF_TARGET_PLATFORMS"] += "\n        <em:targetPlatform>%s</em:targetPlatform>" % target
        install_rdf_path = abspath(join(pythonext_dir, "install.rdf"))
        content = file(install_rdf_path, "r").read()
        for key in ["PYTHONEXT_VERSION", "PYTHON_VERSION",
                    "RDF_TARGET_PLATFORMS", "MOZ_APP_VERSION"]:
            value = package_conf.get(key)
            content = content.replace("$(%s)" % key, value)
        file(install_rdf_path, "w").write(content)

    def _jar(self):
        skin_dir = join(pythonext_dir, "skin")
        zip_recursively(join(pythonext_dir, "pythonext.jar"), [skin_dir], basepath=pythonext_dir, compression=zipfile.ZIP_STORED)
        shutil.rmtree(skin_dir)

    def _set_paths(self):
        xulrunner_dir = abspath("xulrunner-sdk")
        self.xulrunner_bin_dir = join(xulrunner_dir, "bin")
        self.build_bin_dir = join(pyxpcom_obj_dir, "dist", "bin")
        self.moz_xpidl = realpath(join(self.xulrunner_bin_dir, "xpidl"))
        self.moz_idl_dir = join(xulrunner_dir, "idl")
        self.build_lib_dir = join(pyxpcom_obj_dir, "dist", "lib")
        self.build_comp_dir = join(self.build_bin_dir, "components")
        self.build_python_dir = join(self.build_bin_dir, "python")
        self.pythonext_python_dir = join(pythonext_dir, "python")

    def _xpidl(self):
        for idl in glob.glob(join(pythonext_comp_dir, "*.idl")):
            subprocess.check_call([self.moz_xpidl, "-m", "typelib", "-I", self.moz_idl_dir, "-o", os.path.splitext(idl)[0], idl])
            os.remove(idl)

    def _libs(self):
        shutil.copytree(self.build_python_dir, pythonext_lib_dir)
        shutil.copy(realpath(join(self.build_comp_dir, self._dll_name("pyloader"))),
                    join(pythonext_lib_dir, self._dll_name("pyloader")))
        shutil.copy(realpath(join(self.build_comp_dir, self._dll_name("pybootstrap"))),
                    join(pythonext_comp_dir, self._dll_name("pybootstrap")))

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
        filename = "pythonext-%s-%s.xpi" % (package_conf["PYTHONEXT_VERSION"], self._platform_alias)
        zip_recursively(filename, [pythonext_dir], abspath(pythonext_dir), compression=zipfile.ZIP_DEFLATED)

    def package(self):
        self._set_paths()
        self._pre_package()
        self._skeleton()
        self._install_rdf()
        self._jar()
        self._xpidl()
        self._libs()
        self._python()
        self._xpi()


class WinBuild(Build):

    def _pre_configure(self):
        os.environ["PYTHON"] = join(py_install_path, "python.exe").replace("\\", "/")

    def _set_paths(self):
        Build._set_paths(self)
        self.pythonext_python_lib_dir = join(self.pythonext_python_dir, "Lib")

    def _libs(self):
        Build._libs(self)
        shutil.copy(realpath(join(self.build_bin_dir, self._dll_name("pyxpcom"))),
                    join(pythonext_lib_dir, self._dll_name("pyxpcom")))
        shutil.copy(realpath(join(self.build_comp_dir, self._dll_name("pydom"))),
                    join(pythonext_lib_dir, self._dll_name("pydom")))
        shutil.copy(realpath(join(self.build_comp_dir, self._dll_name("pydom_stub"))),
                    join(pythonext_comp_dir, self._dll_name("pydom_stub")))

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

    def _set_paths(self):
        Build._set_paths(self)
        self.pythonext_python_lib_dir = join(self.pythonext_python_dir, "lib", "python%s" % py_ver_dotted)

    def _libs(self):
        Build._libs(self)
        shutil.copy(realpath(join(self.build_lib_dir, self._dll_name("pyxpcom"))),
                    join(pythonext_lib_dir, self._dll_name("pyxpcom")))
        #shutil.copy(realpath(join(self.build_comp_dir, self._dll_name("pydom"))),
        #            join(pythonext_lib_dir, self._dll_name("pydom")))
        #shutil.copy(realpath(join(self.build_comp_dir, self._dll_name("pydom_stub"))),
        #            join(pythonext_comp_dir, self._dll_name("pydom_stub")))

    def _python(self):
        Build._python(self)
        trim(join(self.pythonext_python_dir, "share"))
        self._zip_python(zipfile.PyZipFile(join(self.pythonext_python_dir, "lib", "python%s.zip" % py_ver), "w"))
        os.mkdir(self.pythonext_python_lib_dir)
        python_lib_path = join(py_library_path, "python%s" % py_ver_dotted)
        for dirpath in ("lib-dynload", "config", "plat-linux2"):
            shutil.copytree(join(python_lib_path, dirpath), join(self.pythonext_python_lib_dir, dirpath))


class MacBuild(Build):

    def _update_lib(self, filename, old_library, new_library):
        import stat
        permissions = stat.S_IMODE(os.stat(filename).st_mode)
        if not permissions & stat.S_IWRITE:
            os.chmod(filename, permissions | stat.S_IWRITE)
        subprocess.check_call(["install_name_tool", "-change", old_library, new_library, filename])

    def _pre_configure(self):
        os.environ["PYTHON"] = join(py_install_path, "Python.framework", "Versions", py_ver_dotted, "bin", "python")
        os.environ["DYLD_LIBRARY_PATH"] = py_library_path

    def _pre_package(self):
        Build._pre_package(self, join(pyxpcom_obj_dir, "config", "autoconf.mk"))

    def _set_paths(self):
        Build._set_paths(self)
        self.pythonext_python_dir = join(pythonext_dir, "Frameworks")
        self.pythonext_python_lib_dir = join(self.pythonext_python_dir, "Python.framework", "Versions", py_ver_dotted, "lib", "python%s" % py_ver_dotted)

    def _libs(self):
        Build._libs(self)
        shutil.copy(realpath(join(self.build_comp_dir, self._dll_name("pydom"))),
                    join(pythonext_comp_dir, self._dll_name("pydom")))
        shutil.copy(realpath(join(self.build_lib_dir, self._dll_name("pyxpcom"))),
                    join(pythonext_lib_dir, self._dll_name("pyxpcom")))
        python_library_reference = join(py_install_path, "Python.framework", "Versions", py_ver_dotted, "Python")
        self._update_lib(join(pythonext_lib_dir, self._dll_name("pyxpcom")),
                         python_library_reference,
                         "@loader_path/../Frameworks/Python.framework/Versions/%s/Python" % py_ver_dotted)
        self._update_lib(join(pythonext_lib_dir, self._dll_name("pyloader")),
                         python_library_reference,
                         "@loader_path/../Frameworks/Python.framework/Versions/%s/Python" % py_ver_dotted)
        self._update_lib(join(pythonext_lib_dir, self._dll_name("pyloader")),
                         "@executable_path/libpyxpcom.dylib",
                         "@loader_path/../pylib/libpyxpcom.dylib")
        self._update_lib(join(pythonext_lib_dir, "xpcom", "_xpcom.so"),
                         python_library_reference,
                         "@loader_path/../../Frameworks/Python.framework/Versions/%s/Python" % py_ver_dotted)
        self._update_lib(join(pythonext_lib_dir, "xpcom", "_xpcom.so"),
                         "@executable_path/libpyxpcom.dylib",
                         "@loader_path/../../pylib/libpyxpcom.dylib")
        self._update_lib(join(pythonext_comp_dir, self._dll_name("pydom")),
                         python_library_reference,
                         "@loader_path/../Frameworks/Python.framework/Versions/%s/Python" % py_ver_dotted)
        self._update_lib(join(pythonext_comp_dir, self._dll_name("pydom")),
                         "@executable_path/libpyxpcom.dylib",
                         "@loader_path/../pylib/libpyxpcom.dylib")

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


def main():
    if sys.platform.startswith("win"):
        build = WinBuild()
    elif sys.platform.startswith("linux"):
        build = LinBuild()
    elif sys.platform.startswith("darwin"):
        build = MacBuild()
    else:
        sys.exit("Abort: platform '%s' not supported" % sys.platform)

    # download xulrunner
    build.xulrunner_sdk()

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


if __name__ == "__main__":

    main()

