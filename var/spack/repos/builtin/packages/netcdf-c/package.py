# Copyright 2013-2021 Lawrence Livermore National Security, LLC and other
# Spack Project Developers. See the top-level COPYRIGHT file for details.
#
# SPDX-License-Identifier: (Apache-2.0 OR MIT)

import inspect
import os
import re
from textwrap import dedent
from spack import *
import llnl.util.tty as tty


class NetcdfC(AutotoolsPackage):
    """NetCDF (network Common Data Form) is a set of software libraries and
    machine-independent data formats that support the creation, access, and
    sharing of array-oriented scientific data. This is the C distribution."""

    homepage = "http://www.unidata.ucar.edu/software/netcdf"
    git      = "https://github.com/Unidata/netcdf-c.git"
    url      = "ftp://ftp.unidata.ucar.edu/pub/netcdf/netcdf-c-4.7.3.tar.gz"

    def url_for_version(self, version):
        if version >= Version('4.6.2'):
            url = "ftp://ftp.unidata.ucar.edu/pub/netcdf/netcdf-c-{0}.tar.gz"
        else:
            url = "ftp://ftp.unidata.ucar.edu/pub/netcdf/netcdf-{0}.tar.gz"

        return url.format(version.dotted)

    maintainers = ['skosukhin', 'WardF']

    version('master', branch='master')
    version('4.7.4',   sha256='0e476f00aeed95af8771ff2727b7a15b2de353fb7bb3074a0d340b55c2bd4ea8')
    version('4.7.3',   sha256='8e8c9f4ee15531debcf83788594744bd6553b8489c06a43485a15c93b4e0448b')
    version('4.7.2',   sha256='b751cc1f314ac8357df2e0a1bacf35a624df26fe90981d3ad3fa85a5bbd8989a')
    version('4.7.1',   sha256='5c537c585773e575a16b28c3973b9608a98fdc4cf7c42893aa5223024e0001fc')
    version('4.7.0',   sha256='a512d2b4828c6177dd4b96791c4163e4e06e6bfc7123bebfbfe01762d777d1cb')
    version('4.6.3',   sha256='335fdf16d7531f430ad75e732ed1a9a3fc83ad3ef91fb33a70119a555dd5415c')
    version('4.6.2',   sha256='c37525981167b3cd82d32e1afa3022afb94e59287db5f116c57f5ed4d9c6a638')
    version('4.6.1',   sha256='89c7957458740b763ae828c345240b8a1d29c2c1fed0f065f99b73181b0b2642')
    version('4.6.0',   sha256='4bf05818c1d858224942ae39bfd9c4f1330abec57f04f58b9c3c152065ab3825')
    version('4.5.0',   sha256='cbe70049cf1643c4ad7453f86510811436c9580cb7a1684ada2f32b95b00ca79')
    # Version 4.4.1.1 is having problems in tests
    #    https://github.com/Unidata/netcdf-c/issues/343
    version('4.4.1.1', sha256='4d44c6f4d02a8faf10ea619bfe1ba8224cd993024f4da12988c7465f663c8cae')
    # Version 4.4.1 can crash on you (in real life and in tests).  See:
    #    https://github.com/Unidata/netcdf-c/issues/282
    version('4.4.1',   sha256='8915cc69817f7af6165fbe69a8d1dfe21d5929d7cca9d10b10f568669ec6b342')
    version('4.4.0',   sha256='0d40cb7845abd03c363abcd5f57f16e3c0685a0faf8badb2c59867452f6bcf78')
    version('4.3.3.1', sha256='bdde3d8b0e48eed2948ead65f82c5cfb7590313bc32c4cf6c6546e4cea47ba19')
    version('4.3.3',   sha256='83223ed74423c685a10f6c3cfa15c2d6bf7dc84b46af1e95b9fa862016aaa27e')

    # configure fails if curl is not installed.
    # See https://github.com/Unidata/netcdf-c/issues/1390
    patch('https://github.com/Unidata/netcdf-c/commit/e5315da1e748dc541d50796fb05233da65e86b6b.patch', sha256='10a1c3f7fa05e2c82457482e272bbe04d66d0047b237ad0a73e87d63d848b16c', when='@4.7.0')
    # fix headers
    patch('https://github.com/Unidata/netcdf-c/pull/1505.patch', sha256='f52db13c61b9c19aafe03c2a865163b540e9f6dee36e3a5f808f05fac59f2030', when='@4.7.2')
    patch('https://github.com/Unidata/netcdf-c/pull/1508.patch', sha256='56532470875b9a97f3cf2a7d9ed16ef1612df3265ee38880c109428322ff3a40', when='@4.7.2')

    # See https://github.com/Unidata/netcdf-c/pull/1752
    patch('4.7.3-spectrum-mpi-pnetcdf-detect.patch', when='@4.7.3:4.7.4 +parallel-netcdf')

    variant('mpi', default=True,
            description='Enable parallel I/O for netcdf-4')
    variant('parallel-netcdf', default=False,
            description='Enable parallel I/O for classic files')
    variant('hdf4', default=False, description='Enable HDF4 support')
    variant('pic', default=True,
            description='Produce position-independent code (for shared libs)')
    variant('shared', default=True, description='Enable shared library')
    variant('dap', default=False, description='Enable DAP support')
    variant('jna', default=False, description='Enable JNA support')

    # It's unclear if cdmremote can be enabled if '--enable-netcdf-4' is passed
    # to the configure script. Since netcdf-4 support is mandatory we comment
    # this variant out.
    # variant('cdmremote', default=False,
    #         description='Enable CDM Remote support')

    # The patch for 4.7.0 touches configure.ac. See force_autoreconf below.
    depends_on('autoconf', type='build', when='@4.7.0')
    depends_on('automake', type='build', when='@4.7.0')
    depends_on('libtool', type='build', when='@4.7.0')

    depends_on("m4", type='build')
    depends_on("hdf~netcdf", when='+hdf4')

    # curl 7.18.0 or later is required:
    # http://www.unidata.ucar.edu/software/netcdf/docs/getting_and_building_netcdf.html
    depends_on("curl@7.18.0:", when='+dap')
    # depends_on("curl@7.18.0:", when='+cdmremote')

    depends_on('parallel-netcdf', when='+parallel-netcdf')

    # We need to build with MPI wrappers if any of the two
    # parallel I/O features is enabled:
    # http://www.unidata.ucar.edu/software/netcdf/docs/getting_and_building_netcdf.html#build_parallel
    depends_on('mpi', when='+mpi')
    depends_on('mpi', when='+parallel-netcdf')

    # zlib 1.2.5 or later is required for netCDF-4 compression:
    # http://www.unidata.ucar.edu/software/netcdf/docs/getting_and_building_netcdf.html
    depends_on("zlib@1.2.5:")

    # High-level API of HDF5 1.8.9 or later is required for netCDF-4 support:
    # http://www.unidata.ucar.edu/software/netcdf/docs/getting_and_building_netcdf.html
    depends_on('hdf5@1.8.9:+hl')

    # Starting version 4.4.0, it became possible to disable parallel I/O even
    # if HDF5 supports it. For previous versions of the library we need
    # HDF5 without mpi support to disable parallel I/O:
    depends_on('hdf5~mpi', when='@:4.3~mpi')

    # We need HDF5 with mpi support to enable parallel I/O.
    depends_on('hdf5+mpi', when='+mpi')

    # NetCDF 4.4.0 and prior have compatibility issues with HDF5 1.10 and later
    # https://github.com/Unidata/netcdf-c/issues/250
    depends_on('hdf5@:1.8.999', when='@:4.4.0')

    # The feature was introduced in version 4.1.2
    # and was removed in version 4.4.0
    # conflicts('+cdmremote', when='@:4.1.1,4.4:')

    # The features were introduced in version 4.1.0
    conflicts('+parallel-netcdf', when='@:4.0')
    conflicts('+hdf4', when='@:4.0')

    @property
    def force_autoreconf(self):
        # The patch for 4.7.0 touches configure.ac.
        return self.spec.satisfies('@4.7.0')

    def configure_args(self):
        cflags = []
        cppflags = []
        ldflags = []
        libs = []

        config_args = ['--enable-v2',
                       '--enable-utilities',
                       '--enable-static',
                       '--enable-largefile',
                       '--enable-netcdf-4']

        # The flag was introduced in version 4.1.0
        if self.spec.satisfies('@4.1:'):
            config_args.append('--enable-fsync')

        # The flag was introduced in version 4.3.1
        if self.spec.satisfies('@4.3.1:'):
            config_args.append('--enable-dynamic-loading')

        config_args += self.enable_or_disable('shared')

        if '~shared' in self.spec or '+pic' in self.spec:
            # We don't have shared libraries but we still want it to be
            # possible to use this library in shared builds
            cflags.append(self.compiler.cc_pic_flag)

        config_args += self.enable_or_disable('dap')
        # config_args += self.enable_or_disable('cdmremote')

        # if '+dap' in self.spec or '+cdmremote' in self.spec:
        if '+dap' in self.spec:
            # Make sure Netcdf links against Spack's curl, otherwise it may
            # pick up system's curl, which can give link errors, e.g.:
            # undefined reference to `SSL_CTX_use_certificate_chain_file
            curl = self.spec['curl']
            curl_libs = curl.libs
            libs.append(curl_libs.link_flags)
            ldflags.append(curl_libs.search_flags)
            # TODO: figure out how to get correct flags via headers.cpp_flags
            cppflags.append('-I' + curl.prefix.include)

        if self.spec.satisfies('@4.4:'):
            if '+mpi' in self.spec:
                config_args.append('--enable-parallel4')
            else:
                config_args.append('--disable-parallel4')

        if self.spec.satisfies('@4.3.2:'):
            config_args += self.enable_or_disable('jna')

        # Starting version 4.1.3, --with-hdf5= and other such configure options
        # are removed. Variables CPPFLAGS, LDFLAGS, and LD_LIBRARY_PATH must be
        # used instead.
        hdf5_hl = self.spec['hdf5:hl']
        cppflags.append(hdf5_hl.headers.cpp_flags)
        #ldflags.append(hdf5_hl.libs.search_flags)
        #if hdf5_hl.satisfies('~shared'):
        #    libs.append(hdf5_hl.libs.link_flags)
        #  libs,inc_dirs,lib_dirs
        if hdf5_hl.satisfies('~shared'):
            _libs = {}
            _inc = {}
            _ldirs = {}
            _libs,_inc,_ldirs = self._gather_core_tpl_libraries(['hdf5'],
                                            query_map={'hdf5' : 'hdf5:hl,fortran'},
                                            blacklist_static=['sci_cray'],
                                            shared=False,
                                            wrap_groups=True);
            libs += _libs['hdf5']
            ldflags += ['-L{0}'.format(l) for l in _ldirs['hdf5']] + ['-Wl,--allow-multiple-definition']
        else:
            ldflags.append(hdf5_hl.libs.search_flags)

        if '+parallel-netcdf' in self.spec:
            config_args.append('--enable-pnetcdf')
            pnetcdf = self.spec['parallel-netcdf']
            cppflags.append(pnetcdf.headers.cpp_flags)
            # TODO: change to pnetcdf.libs.search_flags once 'parallel-netcdf'
            # package gets custom implementation of 'libs'
            ldflags.append('-L' + pnetcdf.prefix.lib)
        else:
            config_args.append('--disable-pnetcdf')

        if '+mpi' in self.spec or '+parallel-netcdf' in self.spec:
            config_args.append('CC=%s' % self.spec['mpi'].mpicc)

        config_args += self.enable_or_disable('hdf4')
        if '+hdf4' in self.spec:
            hdf4 = self.spec['hdf']
            cppflags.append(hdf4.headers.cpp_flags)
            # TODO: change to hdf4.libs.search_flags once 'hdf'
            # package gets custom implementation of 'libs' property.
            ldflags.append('-L' + hdf4.prefix.lib)
            # TODO: change to self.spec['jpeg'].libs.link_flags once the
            # implementations of 'jpeg' virtual package get 'jpeg_libs'
            # property.
            libs.append('-ljpeg')
            if '+szip' in hdf4:
                # This should also come from hdf4.libs
                libs.append('-lsz')
            if '+external-xdr' in hdf4 and hdf4['rpc'].name != 'libc':
                libs.append(hdf4['rpc'].libs.link_flags)

        # Fortran support
        # In version 4.2+, NetCDF-C and NetCDF-Fortran have split.
        # Use the netcdf-fortran package to install Fortran support.

        config_args.append('CFLAGS=' + ' '.join(cflags))
        config_args.append('CPPFLAGS=' + ' '.join(cppflags))
        config_args.append('LDFLAGS=' + ' '.join(ldflags))
        config_args.append('LIBS=' + ' '.join(libs))

        return config_args

    def check(self):
        # h5_test fails when run in parallel
        make('check', parallel=False)

    @property
    def libs(self):
        shared = '+shared' in self.spec
        return find_libraries(
            'libnetcdf', root=self.prefix, shared=shared, recursive=True
        )

    def _find_libraries(self,
            dep_name,
            shared=False,
            required_shared=[],
            query_map={},
            override_libnames_map={}):
        spec = self.spec

        banner='*'*80
        # fully qualified paths to the libraries
        libs = []
        inc_dirs = []
        lib_dirs = []
        libnames = []

        # restrict the spec if needed
        if dep_name in query_map:
            spec_query = query_map[dep_name]
            package_spec = spec[query_map[dep_name]]
            #print(f"spec['{spec_query}']")
        else:
            package_spec = spec[dep_name]

        #pprint(package_spec.to_node_dict())
        # extract the libnames
        try:
            #print("spec.libs")
            #pprint(package_spec.libs)

            package_lib_names = package_spec.libs.names

            if dep_name in override_libnames_map:
                package_lib_names = override_libnames_map[dep_name]

            libnames=[ 'lib' + c for c in package_lib_names ]

            # TODO - handle if these are lists or not?
            try:
                inc_dirs = [ package_spec.prefix.include ]
            except:
                pass
            try:
                lib_dirs = [ package_spec.prefix.lib ]
            except:
                pass

            #print('Got libs.names...')
            #pprint(libnames)
        except spack.error.NoLibrariesError:
            # give up if you get none
            return libs,inc_dirs,lib_dirs

        # quit if we got none
        if len(libnames) < 1:
            return libs,inc_dirs,lib_dirs

        txt='''calling find_libraries(
                {names},
                root={root},
                shared={shared},
                recursive=True).split()
            '''
        txt=dedent(txt).format(
                names=libnames,
                root=package_spec.prefix,
                shared=shared)
        #pprint(txt)

        libs = str(find_libraries(libnames,
                                  root=package_spec.prefix,
                                  shared=shared,
                                  recursive=True)).split()
        #pprint(libs)

        #print("++++ Getting dependents...")
        for n in package_spec.dependencies_dict():
            #print('++++' + n)
            #pprint(package_spec[n].to_dict())
            #print("Calling new find libraries with {}".format(n))
            new_libs,new_inc_dirs,new_lib_dirs = self._find_libraries(n,shared)
            #print("Got new libs: {}".format(new_libs))
            libs+=new_libs
            inc_dirs+=new_inc_dirs
            lib_dirs+=new_lib_dirs
        return libs,inc_dirs,lib_dirs

    def _gather_core_tpl_libraries(self,
                                   core_tpls,
                                   query_map={},
                                   override_libnames_map = {},
                                   blacklist_static = [],
                                   shared=False,
                                   required_shared=[],
                                   wrap_groups=False):
        from pathlib import Path

        banner='*'*80
        libs = {}
        inc_dirs = {}
        lib_dirs = {}
        for tpl in core_tpls:
            print(banner)
            print("Calling new find libraries")
            libs[tpl] = []
            inc_dirs[tpl] = []
            lib_dirs[tpl] = []

            libs[tpl],inc_dirs[tpl],lib_dirs[tpl] = \
                self._find_libraries(tpl,
                                     shared=shared,
                                     required_shared=required_shared,
                                     query_map=query_map,
                                     override_libnames_map=override_libnames_map)
            # remove duplicate - this is OKAY if you are use a groups
            inc_dirs[tpl] = list(dict.fromkeys( inc_dirs[tpl] ))
            lib_dirs[tpl] = list(dict.fromkeys( lib_dirs[tpl] ))

            if wrap_groups and len(libs[tpl]) > 1:
                libs[tpl] = list(dict.fromkeys( libs[tpl] ))
                libs[tpl] = ['-Wl,--start-group'] + libs[tpl] + ['-Wl,--end-group']
            # I'd like to handle static/shared better
            # cray requires atleast libsci to be dynamic
            need_fix = False
            if not shared:
                for blacklisted in blacklist_static:
                    if any(blacklisted in l for l in libs[tpl]):
                        need_fix = True
                        break

            if need_fix:
                tty.msg(f"Adjusting TPL: {tpl} Making all sci_cray libraries shared if they are static")
                new_l_prefix = ' '.join([ f'-L{d}' for d in lib_dirs[tpl] ])
                new_libs = []
                for l in libs[tpl]:
                    for blacklisted in blacklist_static:
                        if blacklisted in l:
                            libname = Path(l).name
                            m = re.match('^lib(?P<name>.*)\.a', libname)
                            if m:
                                new_l = m.group('name')
                                new_l = f'-l{new_l}'
                                tty.msg(f"{l} => {new_l}")
                                new_libs.append(new_l)
                            else:
                                tty.msg('WTF: matched {0}, but failed to match lib{1}.a'.format(blacklisted,libname))
                                tty.msg(f'   : lib = {l}')
                                new_libs.append(l)

                libs[tpl] = new_libs

            print("libs = {}".format(libs[tpl]))
            print("inc_dirs = {}".format(inc_dirs[tpl]))
            print("lib_dirs = {}".format(lib_dirs[tpl]))

        print(banner)

        return libs,inc_dirs,lib_dirs

