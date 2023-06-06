# Released under the MIT License. See LICENSE for details.
#
"""A nice collection of ready-to-use pcommands for this package."""
from __future__ import annotations

# Note: import as little as possible here at the module level to
# keep launch times fast for small snippets.
import sys

from efrotools.pcommand import PROJROOT


def gen_monolithic_register_modules() -> None:
    """Generate .h file for registering py modules."""
    import os
    import textwrap

    from efro.error import CleanError
    from batools.featureset import FeatureSet

    if len(sys.argv) != 3:
        raise CleanError('Expected 1 arg.')
    outpath = sys.argv[2]

    featuresets = FeatureSet.get_all_for_project(str(PROJROOT))

    # Filter out ones without native modules.
    featuresets = [f for f in featuresets if f.has_native_python_module]

    pymodulenames = sorted(f.name_python_binary_module for f in featuresets)

    extern_def_code = '\n'.join(
        f'auto PyInit_{n}() -> PyObject*;' for n in pymodulenames
    )
    py_register_code = '\n'.join(
        f'PyImport_AppendInittab("{n}", &PyInit_{n});' for n in pymodulenames
    )
    base_code = """
        // Released under the MIT License. See LICENSE for details.

        #ifndef BALLISTICA_CORE_MGEN_PYTHON_MODULES_MONOLITHIC_H_
        #define BALLISTICA_CORE_MGEN_PYTHON_MODULES_MONOLITHIC_H_

        // THIS CODE IS AUTOGENERATED BY META BUILD; DO NOT EDIT BY HAND.

        #include "ballistica/shared/python/python_sys.h"

        #if BA_MONOLITHIC_BUILD
        extern "C" {
        ${EXTERN_DEF_CODE}
        }
        #endif  // BA_MONOLITHIC_BUILD

        namespace ballistica {

        /// Register init calls for all of our built-in Python modules.
        /// Should only be used in monolithic builds. In modular builds
        /// binary modules get located as .so files on disk as per regular
        /// Python behavior.
        void MonolithicRegisterPythonModules() {
        #if BA_MONOLITHIC_BUILD
        ${PY_REGISTER_CODE}
        #else
          FatalError(
              "MonolithicRegisterPythonModules should not be called"
              " in modular builds.");
        #endif  // BA_MONOLITHIC_BUILD
        }

        }  // namespace ballistica

        #endif  // BALLISTICA_CORE_MGEN_PYTHON_MODULES_MONOLITHIC_H_
        """
    out = (
        textwrap.dedent(base_code)
        .replace('${EXTERN_DEF_CODE}', extern_def_code)
        .replace('${PY_REGISTER_CODE}', textwrap.indent(py_register_code, '  '))
        .strip()
        + '\n'
    )

    os.makedirs(os.path.dirname(outpath), exist_ok=True)
    with open(outpath, 'w', encoding='utf-8') as outfile:
        outfile.write(out)


def stage_server_file() -> None:
    """Stage files for the server environment with some filtering."""
    from efro.error import CleanError
    import batools.assetstaging

    if len(sys.argv) != 5:
        raise CleanError('Expected 3 args (mode, infile, outfile).')
    mode, infilename, outfilename = sys.argv[2], sys.argv[3], sys.argv[4]
    batools.assetstaging.stage_server_file(
        str(PROJROOT), mode, infilename, outfilename
    )


def py_examine() -> None:
    """Run a python examination at a given point in a given file."""
    import os
    from pathlib import Path
    import efrotools

    if len(sys.argv) != 7:
        print('ERROR: expected 7 args')
        sys.exit(255)
    filename = Path(sys.argv[2])
    line = int(sys.argv[3])
    column = int(sys.argv[4])
    selection: str | None = None if sys.argv[5] == '' else sys.argv[5]
    operation = sys.argv[6]

    # This stuff assumes it is being run from project root.
    os.chdir(PROJROOT)

    # Set up pypaths so our main distro stuff works.
    scriptsdir = os.path.abspath(
        os.path.join(
            os.path.dirname(sys.argv[0]), '../src/assets/ba_data/python'
        )
    )
    toolsdir = os.path.abspath(
        os.path.join(os.path.dirname(sys.argv[0]), '../tools')
    )
    if scriptsdir not in sys.path:
        sys.path.append(scriptsdir)
    if toolsdir not in sys.path:
        sys.path.append(toolsdir)
    efrotools.py_examine(PROJROOT, filename, line, column, selection, operation)


def clean_orphaned_assets() -> None:
    """Remove asset files that are no longer part of the build."""
    import os
    import json
    import subprocess

    # Operate from dist root..
    os.chdir(PROJROOT)

    # Our manifest is split into 2 files (public and private)
    with open(
        'src/assets/.asset_manifest_public.json', encoding='utf-8'
    ) as infile:
        manifest = set(json.loads(infile.read()))
    with open(
        'src/assets/.asset_manifest_private.json', encoding='utf-8'
    ) as infile:
        manifest.update(set(json.loads(infile.read())))
    for root, _dirs, fnames in os.walk('build/assets'):
        for fname in fnames:
            fpath = os.path.join(root, fname)
            fpathrel = fpath[13:]  # paths are relative to build/assets
            if fpathrel not in manifest:
                print(f'Removing orphaned asset file: {fpath}')
                os.unlink(fpath)

    # Lastly, clear empty dirs.
    subprocess.run(
        'find build/assets -depth -empty -type d -delete',
        shell=True,
        check=True,
    )


def win_ci_install_prereqs() -> None:
    """Install bits needed for basic win ci."""
    import json
    from efrotools.efrocache import get_target

    # We'll need to pull a handful of things out of efrocache for the
    # build to succeed. Normally this would happen through our Makefile
    # targets but we can't use them under raw window so we need to just
    # hard-code whatever we need here.
    lib_dbg_win32 = 'build/prefab/lib/windows/Debug_Win32'
    needed_targets: set[str] = {
        f'{lib_dbg_win32}/BallisticaKitGenericPlus.lib',
        f'{lib_dbg_win32}/BallisticaKitGenericPlus.pdb',
        'ballisticakit-windows/Generic/BallisticaKit.ico',
    }

    # Look through everything that gets generated by our meta builds
    # and pick out anything we need for our basic builds/tests.
    with open(
        'src/meta/.meta_manifest_public.json', encoding='utf-8'
    ) as infile:
        meta_public: list[str] = json.loads(infile.read())
    with open(
        'src/meta/.meta_manifest_private.json', encoding='utf-8'
    ) as infile:
        meta_private: list[str] = json.loads(infile.read())
    for target in meta_public + meta_private:
        if (target.startswith('src/ballistica/') and '/mgen/' in target) or (
            target.startswith('src/assets/ba_data/python/')
            and '/_mgen/' in target
        ):
            needed_targets.add(target)

    for target in needed_targets:
        get_target(target)


def win_ci_binary_build() -> None:
    """Simple windows binary build for ci."""
    import subprocess

    # Do the thing.
    subprocess.run(
        [
            'C:\\Program Files (x86)\\Microsoft Visual Studio\\2019\\'
            'Enterprise\\MSBuild\\Current\\Bin\\MSBuild.exe',
            'ballisticakit-windows\\Generic\\BallisticaKitGeneric.vcxproj',
            '-target:Build',
            '-property:Configuration=Debug',
            '-property:Platform=Win32',
            '-property:VisualStudioVersion=16',
        ],
        check=True,
    )


def update_cmake_prefab_lib() -> None:
    """Update prefab internal libs for builds."""
    import subprocess
    import os
    from efro.error import CleanError
    import batools.build

    if len(sys.argv) != 5:
        raise CleanError(
            'Expected 3 args (standard/server, debug/release, build-dir)'
        )
    buildtype = sys.argv[2]
    mode = sys.argv[3]
    builddir = sys.argv[4]
    if buildtype not in {'standard', 'server'}:
        raise CleanError(f'Invalid buildtype: {buildtype}')
    if mode not in {'debug', 'release'}:
        raise CleanError(f'Invalid mode: {mode}')
    platform = batools.build.get_current_prefab_platform(
        wsl_gives_windows=False
    )
    suffix = '_server' if buildtype == 'server' else '_gui'
    target = (
        f'build/prefab/lib/{platform}{suffix}/{mode}/' f'libballistica_plus.a'
    )

    # Build the target and then copy it to dst if it doesn't exist there yet
    # or the existing one is older than our target.
    subprocess.run(['make', target], check=True)

    libdir = os.path.join(builddir, 'prefablib')
    libpath = os.path.join(libdir, 'libballistica_plus.a')

    update = True
    time1 = os.path.getmtime(target)
    if os.path.exists(libpath):
        time2 = os.path.getmtime(libpath)
        if time1 <= time2:
            update = False

    if update:
        if not os.path.exists(libdir):
            os.makedirs(libdir, exist_ok=True)
        subprocess.run(['cp', target, libdir], check=True)


def android_archive_unstripped_libs() -> None:
    """Copy libs to a build archive."""
    import subprocess
    from pathlib import Path
    from efro.error import CleanError
    from efro.terminal import Clr

    if len(sys.argv) != 4:
        raise CleanError('Expected 2 args; src-dir and dst-dir')
    src = Path(sys.argv[2])
    dst = Path(sys.argv[3])
    if dst.exists():
        subprocess.run(['rm', '-rf', dst], check=True)
    dst.mkdir(parents=True, exist_ok=True)
    if not src.is_dir():
        raise CleanError(f"Source dir not found: '{src}'")
    libname = 'libmain'
    libext = '.so'
    for abi, abishort in [
        ('armeabi-v7a', 'arm'),
        ('arm64-v8a', 'arm64'),
        ('x86', 'x86'),
        ('x86_64', 'x86-64'),
    ]:
        srcpath = Path(src, abi, libname + libext)
        dstname = f'{libname}_{abishort}{libext}'
        dstpath = Path(dst, dstname)
        if srcpath.exists():
            print(f'Archiving unstripped library: {Clr.BLD}{dstname}{Clr.RST}')
            subprocess.run(['cp', srcpath, dstpath], check=True)
            subprocess.run(
                ['tar', '-zcf', dstname + '.tgz', dstname], cwd=dst, check=True
            )
            subprocess.run(['rm', dstpath], check=True)


def spinoff_test() -> None:
    """Test spinoff functionality."""
    import batools.spinoff

    batools.spinoff.spinoff_test(sys.argv[2:])


def spinoff_check_submodule_parent() -> None:
    """Make sure this dst proj has a submodule parent."""
    import os
    from efro.error import CleanError

    # Make sure we're a spinoff dst project. The spinoff command will be
    # a symlink if this is the case.
    if not os.path.exists('tools/spinoff'):
        raise CleanError(
            'This does not appear to be a spinoff-enabled project.'
        )
    if not os.path.islink('tools/spinoff'):
        raise CleanError('This project is a spinoff parent; we require a dst.')

    if not os.path.isdir('submodules/ballistica'):
        raise CleanError(
            'This project is not using a submodule for its parent.\n'
            'To set one up, run `tools/spinoff add-submodule-parent`'
        )
