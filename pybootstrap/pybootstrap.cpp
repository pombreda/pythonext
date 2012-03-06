/* ***** BEGIN LICENSE BLOCK *****
 * Version: MPL 1.1/GPL 2.0/LGPL 2.1
 * 
 * The contents of this file are subject to the Mozilla Public License
 * Version 1.1 (the "License"); you may not use this file except in
 * compliance with the License. You may obtain a copy of the License at
 * http://www.mozilla.org/MPL/
 * 
 * Software distributed under the License is distributed on an "AS IS"
 * basis, WITHOUT WARRANTY OF ANY KIND, either express or implied. See the
 * License for the specific language governing rights and limitations
 * under the License.
 * 
 * The Original Code is PyXPCOM Extension code.
 * 
 * The Initial Developer of the Original Code is Todd Whiteman.
 * Portions created by the Initial Developer are Copyright (C) 2007-2010.
 * All Rights Reserved.
 * 
 * Contributor(s):
 *   Todd Whiteman <twhitema@gmail.com>
 * 
 * Alternatively, the contents of this file may be used under the terms of
 * either the GNU General Public License Version 2 or later (the "GPL"), or
 * the GNU Lesser General Public License Version 2.1 or later (the "LGPL"),
 * in which case the provisions of the GPL or the LGPL are applicable instead
 * of those above. If you wish to allow use of your version of this file only
 * under the terms of either the GPL or the LGPL, and not to allow others to
 * use your version of this file under the terms of the MPL, indicate your
 * decision by deleting the provisions above and replace them with the notice
 * and other provisions required by the GPL or the LGPL. If you do not delete
 * the provisions above, a recipient may use your version of this file under
 * the terms of any one of the MPL, the GPL or the LGPL.
 * 
 * ***** END LICENSE BLOCK ***** */

/**
 * This XPCOM module dynamically loads the necessary Python libraries
 * before loading the pyxpcom module. This ensures that the correct
 * Python libraries are used in conjunction with the pyxpcom component.
 *
 * Most of this code is based upon Benjamin Smedberg's stub extension example
 * and is Copyright (c) 2005 Benjamin Smedberg <benjamin@smedbergs.us>.
 * Benjamin's original code was retrieved from the Mozilla Developer Center:
 * http://developer.mozilla.org/en/docs/Using_Dependent_Libraries_In_Extension_Components
 */

//
// Layout of the python extension diectory once installed:
//   pyext-directory/components/pybootstrap.dll
//   pyext-directory/components/pydom.dll
//   pyext-directory/pylib/pyloader.dll
//   pyext-directory/pylib/pyxpcom.dll
//   pyext-directory/path/to/python/library (python, python/lib, Frameworks/...)
//

/* Allow logging in the release build */
#ifdef MOZ_LOGGING
#define FORCE_PR_LOG
#endif

#include "prlog.h"
#include "prinit.h"
#include "prerror.h"

#include "nscore.h"
#include "mozilla/ModuleUtils.h"
#include "prlink.h"
#include "nsILocalFile.h"
#include "nsDirectoryServiceUtils.h"
#include "nsStringAPI.h"
#include "nsCOMPtr.h"

#include "nspr.h"

static PRLogModuleInfo *pyBootstrapLog = PR_NewLogModule("pyBootstrapLog");

#define LOG(level, args) PR_LOG(pyBootstrapLog, level, args)


#if defined(XP_MACOSX)
static char kPythonLibrary[] = "Python";
#else
static char kPythonLibrary[] = MOZ_DLL_PREFIX "python" PYTHON_VER MOZ_DLL_SUFFIX;
#endif

static char const *const kPyXPCOMLibraries[] =
{
    MOZ_DLL_PREFIX "pyxpcom" MOZ_DLL_SUFFIX,
    MOZ_DLL_PREFIX "pyloader" MOZ_DLL_SUFFIX,
    nsnull
};

#if defined(XP_UNIX)
const char *kPathSep = ":";
#else
const char *kPathSep = ";";
#endif // XP_UNIX

nsresult
SetEnvPath(const char *var, nsILocalFile *localPath, bool extendPath)
{
    nsCAutoString localBuf;
    char *value;

    localPath->GetNativePath(localBuf);
    
    if(extendPath) {
        value = PR_GetEnv(var);
    }
    
    if(!extendPath || !value || !*value) {
        value = PR_smprintf("%s=%s", var, localBuf.get());
    }
    else {
        value = PR_smprintf("%s=%s%s%s", var, localBuf.get(), kPathSep, value);
    }

    return (PR_SetEnv(value) == PR_SUCCESS) ? NS_OK : NS_ERROR_FAILURE;
}

nsresult
LoadPython(nsILocalFile *pythonPath)
{
    PRLibrary *pythonLib;
#if defined(XP_UNIX) && !defined(XP_MACOSX)
    nsCAutoString pythonBuf;
    PRLibSpec libSpec;

    pythonPath->GetNativePath(pythonBuf);
    libSpec.type = PR_LibSpec_Pathname;
    libSpec.value.pathname = pythonBuf.get();
    pythonLib = PR_LoadLibraryWithFlags(libSpec, PR_LD_GLOBAL | PR_LD_NOW);
#else
    pythonPath->Load(&pythonLib);
#endif // XP_UNIX && !XP_MACOSX

    return (!pythonLib) ? NS_ERROR_FAILURE : NS_OK;
}

// The following line is the one-and-only "NSModule" symbol exported from this
// shared library.
extern "C" { NS_EXPORT const mozilla::Module * NSModule; }

nsresult
InitializeModule(nsIFile *extensionDir)
{
    nsresult rv;
    nsCOMPtr<nsIFile> dir;

    LOG(PR_LOG_DEBUG, ("pybootstrap:: Starting...\n"));

    /* python dir */
    rv = extensionDir->Clone(getter_AddRefs(dir));
    if (NS_FAILED(rv)) {
        LOG(PR_LOG_ERROR, ("pybootstrap:: Couldn't clone nsIFile.\n"));
        return rv;
    }
    nsCOMPtr<nsILocalFile> pythonPath = do_QueryInterface(dir);
    if (!pythonPath) {
        LOG(PR_LOG_ERROR, ("pybootstrap:: Couldn't convert nsIFile to nsILocalFile.\n"));
        return NS_ERROR_FAILURE;
    }

    /* pylib dir */
    rv = extensionDir->Clone(getter_AddRefs(dir));
    if (NS_FAILED(rv)) {
        LOG(PR_LOG_ERROR, ("pybootstrap:: Couldn't clone nsIFile.\n"));
        return rv;
    }
    nsCOMPtr<nsILocalFile> pylibPath = do_QueryInterface(dir);
    if (!pylibPath) {
        LOG(PR_LOG_ERROR, ("pybootstrap:: Couldn't convert nsIFile to nsILocalFile.\n"));
        return NS_ERROR_FAILURE;
    }

    /* set PYTHONHOME */
#if defined(XP_MACOSX)
    pythonPath->AppendNative(NS_LITERAL_CSTRING("Frameworks"));
    pythonPath->AppendNative(NS_LITERAL_CSTRING("Python.framework"));
    pythonPath->AppendNative(NS_LITERAL_CSTRING("Versions"));
    pythonPath->AppendNative(NS_LITERAL_CSTRING(PYTHON_VER));
#else
    pythonPath->AppendNative(NS_LITERAL_CSTRING("python"));
#endif // XP_MACOSX
    rv = SetEnvPath("PYTHONHOME", pythonPath, false);
    if (NS_FAILED(rv)) {
        LOG(PR_LOG_ERROR, ("pybootstrap:: Couldn't set PYTHONHOME environment var!\n"));
        return rv;
    }

    /* set PATH (mandatory on windows) */
    rv = SetEnvPath("PATH", pythonPath, true);
    if (NS_FAILED(rv)) {
        LOG(PR_LOG_ERROR, ("pybootstrap:: Couldn't set PATH environment var!\n"));
        return rv;
    }

    /* set PYTHONPATH */
    pylibPath->AppendNative(NS_LITERAL_CSTRING("pylib"));
    rv = SetEnvPath("PYTHONPATH", pylibPath, true);
    if (NS_FAILED(rv)) {
        LOG(PR_LOG_ERROR, ("pybootstrap:: Couldn't set PYTHONPATH environment var!\n"));
        return rv;
    }

    /* load python */
#if defined(XP_UNIX) && !defined(XP_MACOSX)
    pythonPath->AppendNative(NS_LITERAL_CSTRING("lib"));
#endif // XP_UNIX && !XP_MACOSX
    pythonPath->AppendNative(NS_LITERAL_CSTRING(kPythonLibrary));
    rv = LoadPython(pythonPath);

    nsCString nativePath;
    if (NS_FAILED(rv)) {
        pythonPath->GetNativePath(nativePath);
        LOG(PR_LOG_ERROR, ("pybootstrap:: Couldn't load python lib: '%s'\n", nativePath.get()));
        return rv;
    }

    /* load pyxpcom and pyloader */
    pylibPath->AppendNative(NS_LITERAL_CSTRING("dummy"));
    PRLibrary *pyxpcomLib;
    for (char const *const *libname = kPyXPCOMLibraries; *libname; ++libname) {
        pylibPath->SetNativeLeafName(nsDependentCString(*libname));
        rv = pylibPath->Load(&pyxpcomLib);
        if (NS_FAILED(rv)) {
            pylibPath->GetNativePath(nativePath);
            LOG(PR_LOG_ERROR, ("pybootstrap:: Couldn't load library: '%s'\n", nativePath.get()));
            return rv;
        }
    }

    void *module = PR_FindSymbol(pyxpcomLib, "NSModule");
    if (module) {
        //const mozilla::Module* mData = module;
        NSModule = *(mozilla::Module const *const *) module;
    } else {
        LOG(PR_LOG_ERROR, ("pybootstrap:: Couldn't get NSModule symbol from pyloader!\n"));
        return NS_ERROR_FAILURE;
    }

    LOG(PR_LOG_DEBUG, ("pybootstrap:: Started successfully!\n"));
    return rv;
}




/**
 * This method will be run upon loading of the pybootstrap library.
 * It's job is to initialize the Python environment, load the dependent
 * libraries, and hook up the NSModule to the real pyxpcom loader
 * (mozilla::Module) library.
 */
static int pyxpcom_dependant_library_loader()
{
    // Load dependent libraries
    nsCOMPtr<nsIFile> extensionPath;
    nsresult rv = NS_ERROR_FILE_NOT_FOUND;
    bool locationExists = false;
    char const *const propArray[] = {"ProfD", "GreD", NULL};
    for (char const *const *prop = propArray; *prop; ++prop) {
        NS_GetSpecialDirectory(*prop, getter_AddRefs(extensionPath));
        if (!extensionPath) {
            rv = NS_ERROR_FILE_NOT_FOUND;
            continue;
        }
        rv = extensionPath->AppendNative(NS_LITERAL_CSTRING("extensions"));
        if (NS_FAILED(rv))
            continue;
        rv = extensionPath->AppendNative(NS_LITERAL_CSTRING("pythonext@mozdev.org"));
        if (NS_FAILED(rv))
            continue;
        rv = extensionPath->Exists(&locationExists);
        if (NS_FAILED(rv))
            continue;
        if (!locationExists) {
            rv = NS_ERROR_FILE_NOT_FOUND;
            continue;
        }
        break;
    }
    if (!locationExists) {
        return rv;
    }

    if (PR_LOG_TEST(pyBootstrapLog, PR_LOG_DEBUG)) {
        nsCAutoString path;
        rv = extensionPath->GetNativePath(path);
        printf("pyxpcom_dependant_library_loader:: extensionPath: %s\n", path.get());
    }

    return InitializeModule(extensionPath);
}

// Launch the dependent library loader.
int gIntToInitialize = pyxpcom_dependant_library_loader();

