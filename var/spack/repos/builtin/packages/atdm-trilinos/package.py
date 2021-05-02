# Copyright 2013-2021 Lawrence Livermore National Security, LLC and other
# Spack Project Developers. See the top-level COPYRIGHT file for details.
#
# SPDX-License-Identifier: (Apache-2.0 OR MIT)

import inspect
import os
import re
from textwrap import dedent
import shlex
import subprocess
from pprint import pprint
from spack.util import spack_yaml as s_yaml
from spack import *
# provides module("command", args)
from spack.util.module_cmd import module
from spack.pkg.builtin.kokkos import Kokkos
import llnl.util.tty as tty

import collections


def _atdmtrilinos_load_yaml(file_name, yaml_key=None):
    try:
        with open(file_name) as fptr:
            yaml_data = s_yaml.load(fptr)
            if yaml_key and isinstance(yaml_key, str):
                return yaml_data[yaml_key]
            else:
                return yaml_data

    except IOError:
        tty.die("Error reading %s" % file_name)


def _atdmtrilinos_recursive_update(d, u):
    for k in u:
        v = u[k]
        if isinstance(v, collections.Mapping):
            d[k] = _atdmtrilinos_recursive_update(d.get(k, {}), v)
        else:
            # append notes
            if k == 'note' and k in d:
                d[k] = ('All platforms: {0}. [Platform specific note]: {1}'
                        ''.format(d[k], v))
            else:
                d[k] = v
    return d


def _atdmtrilinos_load_config(platform_name):
    # this is pretty ugly...
    pkg_dir = os.path.abspath(os.path.dirname(__file__))

    policy_file = '{0}/policy.yaml'.format(pkg_dir)
    policy = _atdmtrilinos_load_yaml(policy_file, 'policy')
    platform_file = '{0}/platform/{1}.yaml'.format(pkg_dir, platform_name)
    platform_config = _atdmtrilinos_load_yaml(platform_file, 'platform')

    config = _atdmtrilinos_recursive_update(policy, platform_config[platform_name])

    # we want to massage the config slightly. Virtual packages allow multiple
    # options, but any top level values (that aren't dicts) should be set
    # inside the children
    virtual_packages = ['mpi', 'lapack', 'blas']
    for vpkg in virtual_packages:
        _vconf = config['tpls'].get(vpkg, None)
        if not _vconf:
            continue
        vals = {}
        for k in _vconf:
            v = _vconf[k]
            if not isinstance(v, collections.Mapping):
                vals[k] = v

        # handle the case of no specs (e.g., blas == lapack)
        if len(_vconf) == len(vals):
            # nothing to do, there are no specs
            # so the current dict is all there is
            # add a sentinel value so we know not to expose
            # this to the user
            _vconf['_disable_variant'] = True
            continue

        # if there are specs, then delete the non dicts
        # and copy the single values into the nested dicts
        for k in vals:
            del _vconf[k]

        for spec in _vconf:
            v = _vconf[spec]
            for k in vals:
                if k in v:
                    tty.die('Found duplicate key in top-level virtual package'
                            ' {0} and spec {1}. Key={2}'.format(vpkg, spec, k))
                v[k] = vals[k]

    pprint(config)
    return config


def _atdmtrilinos_default_in_dict(search_map):
    # choose an arbitrary default
    default = list(search_map.keys())[0]
    if len(search_map) == 1:
        return default
    # if there is more than 1 look for a default property
    for k in search_map:
        if search_map[k].get('default', False):
            return k


# This pacakge requires the clingo concretizer in spack
# to enable it,  spack config add "config:concretizer:clingo"
# it requires a GCC to install.
# see spack issue https://github.com/spack/spack/issues/22463
class AtdmTrilinos(CMakePackage):
    """The Trilinos Project is an effort to develop algorithms and enabling
    technologies within an object-oriented software framework for the solution
    of large-scale, complex multi-physics engineering and scientific problems.
    A unique design feature of Trilinos is its focus on packages.
    """
    homepage = "https://trilinos.org/"
    git = "https://github.com/trilinos/Trilinos.git"

    maintainers = ['jjellio']

    platform_name = 'redwood'

    # ###################### Versions ##########################

    version('develop', branch='develop', preferred=True)
    version('13.0.1',
            sha256='0bce7066c27e83085bc189bf524e535e5225636c9ee4b16291a38849d6c2216d')

    # ###################### Variants ###########################
    # whether trilinos should build shared or static libraries
    variant('shared',
            default=False,
            description='Build shared libraries')
    variant('tpls_shared',
            default=False,
            description='Use shared libraries for TPLs')

    # this effectively enables packages
    variant('build_for',
            default='all',
            values=('all', 'sparc', 'empire', 'none'),
            multi=True,
            description=('Build a preset for a given app.'
                         + os.linesep
                         + '  * all will enable all packages.'
                         + os.linesep
                         + '  * sparc will use the ATDM Sparc enables files.'
                         + os.linesep
                         + '  * empire will use the ATDM EMPIRE enables files.'
                         + os.linesep
                         + '  * none means no packages will be explicity enabled,'
                         + ' and you are expected to use `extra_cmake`'))

    variant('tests',
            default=True,
            description="Enable tests and examples")

    variant('package_enables',
            default='none',
            values=('secondary', 'optional', 'none'),
            multi=True,
            description=('Define what level of package dependencies can be'
                         + ' enabled. By defauly, "primary" tested code is enabled.'
                         + ' when you enable a pacakge. (primary is implied and is'
                         + ' not an option). Options may be combined.'
                         + os.linesep
                         + '  * secondary: enables "secondary" tested code'
                         + os.linesep
                         + '  * optional: enable optional packages.'
                         + os.linesep
                         + '  * none: only enable default primary tested code.'
                         + os.linesep
                         + ' See: https://docs.trilinos.org/files/'
                         + 'TrilinosBuildReference.html Sec 5.3'))

    variant('extra_cmake',
            multi=False,
            description=('Provide additional CMake variables (or flags).'
                         ' Use pipe `|` to separate arguments.'),
            default='none')

    # enable complex scalars
    variant('complex', default=False)
    # used with the CI work... will post results as coming from
    # hostname = ci_hostname, this is needed if you build on a node
    # (as you should!)
    variant('ci_hostname',
            multi=False,
            default=platform_name)

    tty.msg("Unifying policy and platform...")
    atdm_config = _atdmtrilinos_load_config(platform_name)

    # control the execution space used
    # for now this is a single value variant
    # it's possible we may use multiple in the future
    # in general, if you enable openmp/cuda/rocm you always get serial as well
    __platform_exec_spaces = atdm_config['exec_spaces']
    variant('exec_space',
            values=tuple(__platform_exec_spaces),
            default=__platform_exec_spaces[0],
            description='the execution space to build.')

    __platform_accel_targets = atdm_config['accel_targets']
    variant('accel_target',
            values=tuple(__platform_accel_targets),
            default=__platform_accel_targets[0],
            multi=False)

    # apply platform depenedencies.
    for depends in atdm_config.get('depends_on', []):
        depends_on(depends['constraint'],
                   type=tuple(depends['type']),
                   when=depends['when'])

    # specify the host side blas/lapack (it assumes they are the same)
    __platform_lapacks = atdm_config['tpls']['lapack']
    if not __platform_lapacks.get('_disable_variant', False):
        __platform_lapacks_default = _atdmtrilinos_default_in_dict(__platform_lapacks)

        variant('host_lapack',
                default=__platform_lapacks_default,
                values=tuple(__platform_lapacks.keys()),
                description='the host blas/lapack to use')

    # specify the mpi (if any)
    __platform_mpis = atdm_config['tpls']['mpi']
    if not __platform_mpis.get('_disable_variant', False):
        __platform_mpis_default = _atdmtrilinos_default_in_dict(__platform_mpis)

        variant('mpi_impl',
                default=__platform_mpis_default,
                values=tuple(__platform_mpis.keys()),
                description='the MPI implementation to use')

    # adding this is causing a the package to depend on the default libsci spec
    # which will the conflict the exec_space=openmp variant
    depends_on('mpi',
               type=('build', 'link', 'run'))
    depends_on('blas',
               type=('build', 'link', 'run'))
    depends_on('lapack',
               type=('build', 'link', 'run'))

    # general dependencies (not in the policy, but they could be)
    # given El Cap will require CMake 3.20 maybe it makes sense
    # we need cmake at +3.19.x for CCE support
    depends_on('cmake@3.19:')
    # my cmake package has a +ninja... maybe that should get committed upstream
    depends_on('ninja@kitware')

    depends_on('python@3:',
               type=('build', 'run'))
    depends_on('perl',
               type=('build', 'run'))

    # ###################### Host Lapack/Blas ##################
    depends_on('cray-libsci~mpi+shared+openmp',
               type=('build', 'link', 'run'),
               when='host_lapack=libsci exec_space=openmp')

    depends_on('cray-libsci~mpi+shared~openmp',
               type=('build', 'link', 'run'),
               when='exec_space=serial host_lapack=libsci')

    # ###################### Variants ##########################
    tpl_build_type = 'Release'
    tpl_variant_map = {
        'netcdf-c': {
            'version': '',
            'variant': '~hdf4~jna~dap'  # disable dap because curl/idn2 is bugged
                       '+mpi+parallel-netcdf'
                       ' build_type=' + tpl_build_type
            },
        'hdf5': {
            'version': '@1.10.7',
            'variant': '~cxx~debug~threadsafe~java'
                       '+fortran+hl+mpi+szip'
                       ' build_type=' + tpl_build_type
            },
        'parallel-netcdf': {
            'version': '',
            'variant': '~cxx~burstbuffer'
                       '+fortran'
                       ' build_type=' + tpl_build_type
            },
        'parmetis': {
            'version': '@4.0.3',
            'variant': '~gdb~ipo'
                       '+ninja+int64'
                       ' build_type=' + tpl_build_type
            },
        'metis': {
            'version': '@5:',
            'variant': '~gdb'
                       '+int64~real64'
                       ' build_type=' + tpl_build_type
            },
        'cgns': {
            'version': '',
            'variant': '~base_scope~int64~ipo~legacy~mem_debug~fortran'
                       '+hdf5+mpi+parallel+scoping+static'
                       ' build_type=' + tpl_build_type
            },
        'boost': {
            'version': '',
            'variant': '+system+icu cxxstd=11'
                       ''  # Boost is neither Cmake or AutoTools
            },
        'superlu-dist': {
            'version': '@6.4.0',
            'variant': '~ipo~int64'
                       ' build_type=' + tpl_build_type
            },
        }

    tty.debug('Determining Trilinos requirements for third party libraries (tpls)')
    for tpl, tpl_config in tpl_variant_map.items():
        vers = tpl_config["version"]
        opts = tpl_config['variant']
        tty.debug(f'{tpl} : version = {vers if vers else "any"}')
        tty.debug(f'      : variant = {opts}')
        depends_on(f'{tpl}{vers}{opts}',
                   type=('build', 'link', 'run'))
        if tpl not in ['cgns']:
            depends_on(f'{tpl}+shared', when='+tpls_shared')
            depends_on(f'{tpl}~shared', when='~tpls_shared')

    # this depends on concretizer = clingo
    # with that new concretizer, spack will realize that we have declared
    # a lapack/blas provider (in libsci), and then enforce that dependencies
    # use the declared provider (and spec).
    depends_on('superlu-dist+openmp',
               type=('build', 'link', 'run'),
               when='exec_space=openmp')
    depends_on('superlu-dist~openmp',
               type=('build', 'link', 'run'),
               when='exec_space=serial')
    # without clingo, I tried this... which caused the conretizer to go into an
    # infinite loop
    # depends_on('superlu-dist@6.4.0~ipo~int64+shared+openmp^cray-libsci+openmp',
    #                type=('build', 'link', 'run'),
    #                when='exec_space=openmp host_lapack=libsci')
    # depends_on('superlu-dist@6.4.0~ipo~int64+shared~openmp^cray-libsci~openmp',
    #                type=('build', 'link', 'run'),
    #                when='exec_space=serial host_lapack=libsci')

    patch('cray_secas.patch')
    patch('atdm-env-add-hip.patch')
    patch('fix-atdm-dev-env-parmetis.patch')
    # patch('shylu.patch')
    # piro include test
    patch('https://github.com/jjellio/Trilinos/commit/a82a80df2ec982b3073a03b257fcc3688e4e0542.patch',
          sha256='d6d1d2f6e9f4a3e2a7a30bb4b718499633ddfc20992069e3fb0b03e70a45bee4')
    # build stats
    patch('8638.patch',
          sha256='0f845ed22b262a98d216954d898c8ffdaad79fbace819f9b50f5b15a177c15a1')

    def url_for_version(self, version):
        url = "https://github.com/trilinos/Trilinos/archive/trilinos-release-{0}.tar.gz"
        return url.format(version.dashed)

    def cmake_args(self):
        spec = self.spec
        define = CMakePackage.define
        options = []
        disable_options = {}

        # import traceback
        # traceback.print_stack()

        # define the max number of MPI procs a test can require
        trilinos_test_max_num_procs = 16

        build_for = spec.variants['build_for']
        opt_file = 'cmake/std/atdm/ATDMDevEnv.cmake'
        if 'empire' in build_for:
            opt_file += ';cmake/std/atdm/apps/empire/EMPIRETrilinosEnables.cmake'

        if 'sparc' in build_for:
            opt_file += ';cmake/std/atdm/apps/sparc/SPARCTrilinosPackagesEnables.cmake'

        if 'all' in build_for:
            options.extend([
                define('Trilinos_ENABLE_ALL_PACKAGES', True),
                ])

        if '+tests' in spec:
            options.extend([
                define('Trilinos_ENABLE_TESTS', True),
                define('Trilinos_ENABLE_EXAMPLES', True),
                ])

        package_enables = spec.variants['package_enables']
        if 'secondary' in package_enables:
            options.extend([
                define('Trilinos_ENABLE_SECONDARY_TESTED_CODE', True),
                ])

        if 'optional' in package_enables:
            options.extend([
                define('Trilinos_ENABLE_ALL_OPTIONAL_PACKAGES', True),
                ])

        # add extra cmake parameters verbatim
        extra_cmake = spec.variants['extra_cmake'].value
        if extra_cmake:
            options += [extra for extra in extra_cmake.split('|')
                        if extra.lower() != 'none']

        # try to be static if asked to be
        if '~tpl_shared' in spec:
            options += [define('CMAKE_FIND_LIBRARY_SUFFIXES', '.a;.so')]

        options.extend([
            define('Trilinos_WARNINGS_AS_ERRORS_FLAGS', ''),
            define('Trilinos_ALLOW_NO_PACKAGES', True),
            define('Trilinos_DISABLE_ENABLED_FORWARD_DEP_PACKAGES', True),
            define('Trilinos_DEPS_XML_OUTPUT_FILE', ''),
            define('Trilinos_EXTRAREPOS_FILE', ''),
            define('Trilinos_IGNORE_MISSING_EXTRA_REPOSITORIES', True),
            define('Trilinos_ENABLE_KNOWN_EXTERNAL_REPOS_TYPE', 'None'),
            define('CMAKE_VERBOSE_MAKEFILE', False),
            define('CMAKE_CXX_LINK_FLAGS', '-fuse-ld=lld -Wl,--threads=8'),
            define('CMAKE_C_LINK_FLAGS', '-fuse-ld=lld -Wl,--threads=8'),
            define('Trilinos_TRACE_ADD_TEST', True),
            define('Trilinos_ENABLE_CONFIGURE_TIMING', True),
            define('Trilinos_HOSTNAME', spec.variants['ci_hostname'].value),
            define('Trilinos_CONFIGURE_OPTIONS_FILE', opt_file),
            define('Trilinos_ENABLE_BUILD_STATS', False),
            define('MPI_EXEC_MAX_NUMPROCS', trilinos_test_max_num_procs),
            define('DART_TESTING_TIMEOUT', 200),
            ])

        for disable_opt in disable_options:
            options += [define(disable_opt, False)]

        return options

    @property
    def std_cmake_args(self):
        """This allows the Ninja generator to be set based on the spec
        :return: standard cmake arguments
        """
        # standard CMake arguments
        if "+ninja" in self.spec:
            CMakePackage.generator = "Ninja"

        std_cmake_args = CMakePackage._std_args(self)

        # std_cmake_args += getattr(self, 'cmake_flag_args', [])
        return std_cmake_args

    def build(self, spec, prefix):
        """Make the build targets"""
        with working_dir(self.build_directory):
            if self.generator == 'Unix Makefiles':
                inspect.getmodule(self).make(*self.build_targets, '-ik',
                                             fail_on_error=False)
            elif self.generator == 'Ninja':
                inspect.getmodule(self).ninja(*self.build_targets, '-k 0',
                                              fail_on_error=False)

    def cmake(self, spec, prefix):
        tty.msg("Preparing ATDM environment in setup_build_environment")
        tty.msg("  which(mpicxx): {0}".format(which("mpicxx")))
        spack_env_dir = self._write_spack_magic()
        self._source_spack_magic_and_add_env(spack_env_dir, env)

        print("++++========== ////      ||||     \\\\\\\\ ================== ++++++")
        print(" Calling cmake hook:")
        print("Current ATDM_CONFIG_COMPLETED_ENV_SETUP = {0}"
              "".format(os.environ.get('ATDM_CONFIG_COMPLETED_ENV_SETUP', 'unset')))

        # atdm config source location
        trilinos_src = self.stage.source_path
        os.system("ls -l {}".format(trilinos_src))

        tty.msg("ATDM_CONFIG_CUSTOM_CONFIG_DIR = {}"
                "".format(os.environ.get('ATDM_CONFIG_CUSTOM_CONFIG_DIR', 'unset')))
        if 'ATDM_CONFIG_CUSTOM_CONFIG_DIR' in os.environ:
            spack_env_dir     = os.environ['ATDM_CONFIG_CUSTOM_CONFIG_DIR']
            lcl_spack_env_dir = spack_env_dir  # os.path.basename(spack_env_dir)
            dest_dir = '{0}/cmake/std/atdm/{1}'.format(trilinos_src,
                                                       os.path.basename(spack_env_dir))
            cwd = os.getcwd()
            tty.msg("Copying spack magic environment into Trilinos")
            tty.msg(f"Current directory: {cwd}")
            tty.msg(f'cp -vr {lcl_spack_env_dir} {dest_dir}')
            os.system(f'cp -vr {lcl_spack_env_dir} {dest_dir}')
            os.system(f'ls -l {dest_dir}')

        loaded_modules=module("list")
        tty.msg("\n\n\n\n==========================================\n"
                "calling cmake\n"
                "  module list:\n "
                "{0}"
                "".format(loaded_modules))
        super(AtdmTrilinos, self).cmake(spec, prefix)

    def setup_build_environment(self, spack_env):
        spec = self.spec
        if '+mpi' in spec:
            tty.msg("MPI Include: %s" % spec['mpi'].prefix.include)
            tty.msg("MPI Libdir:  %s" % spec['mpi'].prefix.lib)
            tty.msg("MPI libraries: %s" % spec['mpi'].libs.names)
            tty.msg("MPI dirs: %s" % spec['mpi'].libs.directories)
            tty.msg("CC : %s" % spec['mpi'].mpicc)
            tty.msg("CXX: %s" % spec['mpi'].mpicxx)
            tty.msg("FC : %s" % spec['mpi'].mpifc)
            os.system('module list')

        #tty.msg("Preparing ATDM environment in setup_build_environment")
        #spack_env_dir = self._write_spack_magic()
        #self._source_spack_magic_and_add_env(spack_env_dir, spack_env)

    def _write_spack_magic(self, spack_magic_name='spack_magic'):
        tty.msg("Generating ATDM config environment called {}".format(spack_magic_name))

        # write into Trilinos_src/cmake/std/atdm (we don't technically need to)
        # trilinos doesn't exists yet.. so make it in cwd()
        spack_env_dir = '/tmp/{0}'.format(spack_magic_name)
        tty.msg('Generating ATDM config, creating directory: {0}'
                ''.format(spack_env_dir))
        try:
            os.mkdir(spack_env_dir)
        except FileExistsError:
            pass

        self._write_spack_magic_trilinos_env(spack_env_dir)
        self._write_spack_magic_custom_builds(spack_env_dir)

        spack_env_file = '{0}/environment.sh'.format(spack_env_dir)
        os.system("ls -l {0}".format(spack_env_dir))
        os.system("echo {0}".format(spack_env_file))
        os.system("cat {0}".format(spack_env_file))

        return spack_env_dir

    def _get_atdm_compiler_config_name(self):
        """
        This is not strictly necessary, but this allows us to express a
        'config name' for the recipe we are about to build.  By default,
        Trilinos uses some well defined names that map directly to CDash
        dashboards.

        For now we want to capture things like accelerator, compiler, and
        MPI names/versions

        Data is written to
          {spack_env_dir}/custom_builds.sh
          export ATDM_CONFIG_COMPILER={compiler_name}-{compiler_version}_
                                      {mpi_name}-{mpi_version}[-{more}...]
        """
        exec_space = self.spec.variants['exec_space'].value

        compiler_name, compiler_version = self._get_compiler_name_version()
        atdm_config_name = '{0}-{1}'.format(compiler_name, compiler_version)
        if exec_space == 'rocm':
            rocm_name, rocm_version = self._get_true_name_version('rocm')
            atdm_config_name += '_{0}-{1}'.format(rocm_name, rocm_version)
        elif exec_space == 'openmp':
            atdm_config_name += '_openmp'

        mpi_name, mpi_version = self._get_true_name_version('mpi')
        atdm_config_name += '_{0}-{1}'.format(mpi_name, mpi_version)

        return atdm_config_name

    def _write_spack_magic_custom_builds(self, spack_magic_dir):

        atdm_config_name = self._get_atdm_compiler_config_name()

        template = """
        # write to spack_env_dir/custom_builds.sh
        export ATDM_CONFIG_COMPILER="{0}"
        """.format(atdm_config_name)

        tty.msg("Writing ATDM config custom_builds.sh")
        tty.msg(f"Chose ATDM_CONFIG_COMPILER={atdm_config_name}")

        spack_compiler_file = '{0}/custom_builds.sh'.format(spack_magic_dir)
        with open(spack_compiler_file, "w") as fptr:
            fptr.write(dedent(template))

    def _create_spack_atdm_env(self):

        # we need another mapping from spack names to Trilinos ENV names
        # these are asserted in ATDMDevSettings
        # ROOT variables are easy - they are spack.prefix
        '''
            ASSERT_DEFINED(ENV{ATDM_CONFIG_BLAS_LIBS})
            ASSERT_DEFINED(ENV{ATDM_CONFIG_LAPACK_LIBS})
            ASSERT_DEFINED(ENV{BOOST_ROOT})
            ASSERT_DEFINED(ENV{HDF5_ROOT})
            ASSERT_DEFINED(ENV{NETCDF_ROOT})

            IF (ATDM_ENABLE_SPARC_SETTINGS)
              ASSERT_DEFINED(ENV{ATDM_CONFIG_BINUTILS_LIBS})
              ASSERT_DEFINED(ENV{METIS_ROOT})
              ASSERT_DEFINED(ENV{PARMETIS_ROOT})
              ASSERT_DEFINED(ENV{PNETCDF_ROOT})
              ASSERT_DEFINED(ENV{CGNS_ROOT})
              ASSERT_DEFINED(ENV{ATDM_CONFIG_SUPERLUDIST_INCLUDE_DIRS})
              ASSERT_DEFINED(ENV{ATDM_CONFIG_SUPERLUDIST_LIBS})
            ENDIF()

            ATDM_SET_ENABLE(TPL_BinUtils_LIBRARIES "$ENV{ATDM_CONFIG_BINUTILS_LIBS}")

            ATDM_SET_CACHE(TPL_BLAS_LIBRARIES "$ENV{ATDM_CONFIG_BLAS_LIBS}"
                           CACHE FILEPATH)
            ATDM_SET_CACHE(TPL_LAPACK_LIBRARIES "$ENV{ATDM_CONFIG_LAPACK_LIBS}"
                           CACHE FILEPATH)

            #
            # maybe best to ignore boost... they hardcode the paths as-is
            #
            ATDM_SET_CACHE(TPL_Boost_LIBRARIES
               "$ENV{BOOST_ROOT}/lib/libboost_program_options.${ATDM_TPL_LIB_EXT};
                $ENV{BOOST_ROOT}/lib/libboost_system.${ATDM_TPL_LIB_EXT}"
              CACHE FILEPATH)

            # BoostLib
            IF (NOT "$ENV{ATDM_CONFIG_BOOST_LIBS}" STREQUAL "")
              ATDM_SET_CACHE(TPL_BoostLib_LIBRARIES "$ENV{ATDM_CONFIG_BOOST_LIBS}"
                             CACHE FILEPATH)
            ELSE()
              ATDM_SET_CACHE(TPL_BoostLib_LIBRARIES
                "$ENV{BOOST_ROOT}/lib/libboost_program_options.${ATDM_TPL_LIB_EXT};
                 $ENV{BOOST_ROOT}/lib/libboost_system.${ATDM_TPL_LIB_EXT}"
                CACHE FILEPATH)
            ENDIF()

            # METIS
            ATDM_SET_CACHE(TPL_METIS_LIBRARIES "$ENV{ATDM_CONFIG_METIS_LIBS}"
                           CACHE FILEPATH)

            # ParMETIS
            ATDM_SET_CACHE(TPL_ParMETIS_LIBRARIES "$ENV{ATDM_CONFIG_PARMETIS_LIBS}"
                           CACHE FILEPATH)

            # CGNS
            IF (NOT "$ENV{ATDM_CONFIG_CGNS_LIBRARY_NAMES}" STREQUAL "")
              ATDM_SET_CACHE(CGNS_LIBRARY_NAMES
                             "$ENV{ATDM_CONFIG_CGNS_LIBRARY_NAMES}" CACHE FILEPATH)
            ENDIF()
            ATDM_SET_CACHE(TPL_CGNS_LIBRARIES "$ENV{ATDM_CONFIG_CGNS_LIBS}"
                           CACHE FILEPATH)

            # HDF5
              ATDM_SET_CACHE(TPL_HDF5_LIBRARIES "$ENV{ATDM_CONFIG_HDF5_LIBS}"
                             CACHE FILEPATH)

            # Netcdf
                ATDM_SET_CACHE(TPL_Netcdf_LIBRARIES "$ENV{ATDM_CONFIG_NETCDF_LIBS}"
                               CACHE FILEPATH)

            # SuperLUDist
            ATDM_SET_CACHE(SuperLUDist_INCLUDE_DIRS
                           "$ENV{ATDM_CONFIG_SUPERLUDIST_INCLUDE_DIRS}"
                           CACHE FILEPATH)
            ATDM_SET_CACHE(TPL_SuperLUDist_LIBRARIES
                           "$ENV{ATDM_CONFIG_SUPERLUDIST_LIBS}" CACHE FILEPATH)

            # many inconsistencies here
            SuperLUDist doens't work using ROOT for includes
            Boost doesn't use libraries but boostlib does
        '''

        # map spack names to Trilinos NAMES
        core_tpls = {'hdf5':             'HDF5',
                     'netcdf-c':         'NETCDF',
                     'parallel-netcdf':  'PNETCDF',
                     'boost':            'BOOST',
                     'cgns':             'CGNS',
                     'metis':            'METIS',
                     'parmetis':         'PARMETIS',
                     'superlu-dist':     'SUPERLUDIST',
                     'blas':             'BLAS',
                     'lapack':           'LAPACK'}

        # this is an expensive call
        # returns a map of spack dependencies and their libraries if
        # shared=False, then we should use them as-is if we instead want
        # -L/path -lfoo -lbar then we we should loop through each list of
        # libraries and compute the directories and libnames

        # define the configuration to search for
        shared = False
        wrap_groups = True
        # spack query syntax, key is the spec name, value is a query
        query_map = {'hdf5':  'hdf5:hl,fortran',
                     'boost': 'boost:system,program_options'}
        # return these lirbary names only
        override_libnames_map = {'boost': ['boost_system',
                                           'boost_program_options']}
        # define libraries that can't be static (not robust!)
        blacklist_static = ['sci_cray']

        # handle if we want shared linkage instead
        if '+tpls_shared' in self.spec:
            shared = True
            wrap_groups = False

        # make the library find call
        tpl_libs, tpl_incs, tpl_libdirs = \
            self._gather_core_tpl_libraries(
                core_tpls=core_tpls.keys(),
                query_map=query_map,
                override_libnames_map=override_libnames_map,
                blacklist_static=blacklist_static,
                shared=shared,
                wrap_groups=wrap_groups)

        # this needs to be better - we generate the lines of the
        # atdm/environment.sh.  We could probably write this out as format
        # file, then read in the file as string, apply formatting, and
        # that's it.
        # TODO: create template file
        # replace code here with setting a map
        env_lines = []
        txt = '''
            # This is an auto-generated file used to mimic the
            # 'source -> configure -> build' method used by some workflows
            # including EMPIRE and Trilinos CI at Sandia
            echo "Inside fake env"
            '''
        env_lines.append(dedent(txt))

        # config_map = {}
        # config_lines = []

        # do modules first
        module_blob = '\n'.join(module("list -t").splitlines()[1:])
        txt = '''
        # module stuff

        module purge
        load_modules=({module_blob})
        module load "${{load_modules[@]}}"
        unwanted_modules=()
        loaded_modules=($(module list -t | tail -n+2))
        for m in "${{loaded_modules[@]}}"; do
          valid=false
          for valid_module in "${{load_modules[@]}}"; do
            if [ "$valid_module" == "$m" ]; then
              valid=true
            fi
          done
          if [ "$valid" == "false" ]; then
            module rm $m
          fi
        done
        '''.format(module_blob=module_blob)
        env_lines.append(dedent(txt))

        # setup our variables
        # ideally we'd like to module load tpl-exec_space, and have it do all of
        # this. Currently, spack's module naming isn't making the required
        # modules alternatively, we could maybe add a meta-moduled,
        # atdm-dev-exec_space... this would all look much better
        for spec_name, atdm_name in core_tpls.items():
            prefix = self.spec[spec_name].prefix
            # cmake wants semicolon delimited lists
            inc_dirs = ';'.join(tpl_incs[spec_name])
            libs = ';'.join(tpl_libs[spec_name])

            # lib_dirs... would need to do something..
            # lib_names... I wouldn't set this, set libs to -Ldirs;libnames
            txt = f'''
            _spack_{atdm_name}_ROOT="{prefix}"
            : "${{{atdm_name}_ROOT:=${{_spack_{atdm_name}_ROOT}}}}"
            unset _spack_{atdm_name}_ROOT
            export {atdm_name}_ROOT

            export ATDM_CONFIG_{atdm_name}_INCLUDE_DIRS="{inc_dirs}"
            export ATDM_CONFIG_{atdm_name}_LIBS="{libs}"
            '''
            env_lines.append(dedent(txt))

        # this sucks - Cray provides bin utils for all CCE, but spack can't
        # understand that. Ideally, you could make a package that is aware that
        # it is controlled by the compiler module but if you module load CCE in
        # that package you are hosed
        # I don't know what you are supposed to do..
        txt = '''# yuck
            export BINUTILS_ROOT={bin_utils_root}
            # leaving this off for now... this could be evil
            export ATDM_CONFIG_BINUTILS_LIBS="-L${{BINUTILS_ROOT}}/lib;-lbfd"
            '''.format(bin_utils_root=os.environ.get('CRAY_BINUTILS_ROOT', ''))

        env_lines.append(dedent(txt))

        # we've handled libraries, now do the compilers
        # self.compilers.modules contains the loaded compiler modules
        compiler_modules = dict.fromkeys(self.compiler.modules)
        compiler_modules = list(self.compiler.modules)
        txt = '''
            # can't do this yet...
            #module purge &>/dev/null
            #module load {0}
            '''.format(' '.join(compiler_modules))
        env_lines.append(dedent(txt))

        # there is a LLNL module for querying micro arch...
        # but we want to use whatever we are targetting via Cray
        # spack should really provide support for module based microarch
        # compiling. e.g., craype-x86-haswell
        if 'CRAY_CPU_TARGET' in os.environ:
            # this will throw if the ENV isn't set... so spack better be nice
            # with cray!
            kokkos_arch = self.targets_to_kokkos_map[os.environ['CRAY_CPU_TARGET']]
            tty.msg('Setting Kokkos_ARCH using CrayPE ... got {0}'
                    ''.format(kokkos_arch))
        else:
            kokkos_arch = \
                Kokkos.spack_micro_arch_map[self.spec.target.name].upper()
            tty.msg('Setting Kokkos_ARCH using spec.target.name ... got {0}'
                    ''.format(kokkos_arch))

        if self.spec.variants['accel_target'].value != 'none':
            if 'CRAY_ACCEL_TARGET' in os.environ:
                # this will throw if the ENV isn't set... so spack better be nice
                # with cray!
                kokkos_arch += ';' + self.targets_to_kokkos_map[os.environ['CRAY_ACCEL_TARGET']]
                tty.msg('Setting Kokkos_ARCH using CrayPE ... got {0}'
                        ''.format(kokkos_arch))
            else:
                tty.error('CRAY_ACCEL_TARGET is not defined!')
                os.system("module list")
                exit(-1)

        import string
        class BlankFormatter(string.Formatter):
            def __init__(self, default=''):
                self.default=default

            def get_value(self, key, args, kwds):
                if isinstance(key, str):
                    return kwds.get(key, self.default)
                else:
                    return string.Formatter.get_value(key, args, kwds)

        config_map = {}
        variants = self.spec.variants

        config_map['atdm_config_kokkos_arch'] = kokkos_arch

        config_map["ci_hostname"] = variants['ci_hostname'].value
        config_map["mpiexec_flags"] = ''
        config_map["mpiexec_np"] = '-n'
        # need to fix this
        config_map["mpiexec"] = which('srun')
        # markup the compilers used
        config_map["mpicc"] = self.compiler.cc
        config_map["mpicxx"] = self.compiler.cxx
        config_map["mpif90"] = self.compiler.fc

        config_map["spack_magic"] = 'spack_magic'
        config_map["spack_magic_dir"] = '/tmp/{spack_magic}'.format(**config_map)
        config_map["exec_space"] = str(variants['exec_space'].value).lower()
        config_map["kokkos_node_type"] = config_map["exec_space"]
        config_map["atdm_config_trilinos_dir"] = self.prefix

        config_map["atdm_config_build_type_l"] = variants['build_type'].value.lower()
        config_map["atdm_config_build_type"] = variants['build_type'].value.upper()
        # this is the weird name from custom-builds.sh
        config_map["atdm_config_compiler"] = self._get_atdm_compiler_config_name()
        # this is the 'build name' givin to load-env
        config_map["atdm_config_build_name"] = ('{spack_magic}-'
                                                '{atdm_config_compiler}-'
                                                '{atdm_config_build_type_l}-'
                                                '{kokkos_node_type}'
                                                ''.format(**config_map))

        if variants['complex'].value:
            config_map["atdm_config_enable_complex"] = 'ON'
            config_map["atdm_config_build_name"] += '-complex'
        else:
            config_map["atdm_config_enable_complex"] = 'OFF'

        if variants['shared'].value:
            config_map["atdm_config_build_name"] += '-shared'
            config_map["atdm_config_build_shared_libs"] = 'ON'
        else:
            config_map["atdm_config_build_shared_libs"] = 'OFF'

        if config_map['exec_space'] == 'openmp':
            config_map["atdm_config_use_openmp"] = 'ON'
        else:
            config_map["atdm_config_use_openmp"] = 'OFF'

        if config_map['exec_space'] == 'cuda':
            config_map["atdm_config_use_cuda"] = 'ON'
        else:
            config_map["atdm_config_use_cuda"] = 'OFF'

        if config_map['exec_space'] == 'hip':
            config_map["atdm_config_use_hip"] = 'ON'
            config_map["atdm_config_hip_root"] = env['HIP_PATH']

            # this is a mixed toolchain thing...
            config_map["atdm_config_override_mpicxx"] = which("mpicxx")
            config_map["atdm_config_override_mpicxx_inner_compiler"] = which("hipcc")

        else:
            config_map["atdm_config_use_hip"] = 'OFF'
            config_map["atdm_config_hip_root"] = ''

        # be aware - to mimic an SNL build, we create, then source this all back in
        # we only propagate back into the SPACK env ATDM_CONFIG variables
        # and [A-Za-z]+_ROOT variables
        # I've added a special case for MPICC, MPICXX, and MPIF90
        # That list of special variables had to grow to MPICH_CXX and OMPI_CXX
        #
        # This is a bit of a headache. I explicitly *want* this ENV file to drive the
        # environment - not by manually setting ENVs in spack.
        #
        # The gimick works by source this, matching ENVs I white list above
        # then setting them inside spack's `env` variable
        txt = '''
            # this is an internal variable that enables the libraries common to both
            # sparc and empire ... it's name predates empire using it
            export ATDM_CONFIG_ENABLE_SPARC_SETTINGS=ON
            export ATDM_CONFIG_USE_SPARC_TPL_FIND_SETTINGS=OFF

            # override the hostnames used... hopefully this helps cdash work
            export ATDM_CONFIG_KNOWN_HOSTNAME={ci_hostname}
            export ATDM_CONFIG_CDASH_HOSTNAME={ci_hostname}
            export ATDM_CONFIG_REAL_HOSTNAME={ci_hostname}

            # this doesn't do anything outside test scripts
            export ATDM_CONFIG_USE_NINJA=ON

            #Not sure if we need these... they may get auto set
            # they are set in ats2
            # ATDM Settings
            export ATDM_CONFIG_KOKKOS_ARCH="{atdm_config_kokkos_arch}"
            export ATDM_CONFIG_CUDA_RDC="OFF"
            export ATDM_CONFIG_USE_HIP={atdm_config_use_hip}
            export ATDM_CONFIG_USE_CUDA={atdm_config_use_cuda}
            export ATDM_CONFIG_USE_OPENMP={atdm_config_use_openmp}
            export ATDM_CONFIG_USE_PTHREADS=OFF
            export ATDM_CONFIG_CTEST_PARALLEL_LEVEL=4
            export ATDM_CONFIG_BUILD_COUNT=60
            export ATDM_CONFIG_FPIC="OFF"

            export ATDM_CONFIG_OVERRIDE_MPICXX="{atdm_config_override_mpicxx}"
            export ATDM_CONFIG_OVERRIDE_MPICXX_INNER_COMPILER="{atdm_config_override_mpicxx_inner_compiler}"

            if [ "$ATDM_CONFIG_USE_HIP" == "ON" ]; then
              # set HIP_ROOT if it is not defined
              : "${{HIP_ROOT:={atdm_config_hip_root}}}"
              export HIP_ROOT
              export ATDM_CONFIG_HIP_ROOT="$HIP_ROOT"
            fi

            # Kokkos Settings
            export ATDM_CONFIG_Kokkos_ENABLE_SERIAL=ON
            #export KOKKOS_NUM_DEVICES=4

            # Set common MPI wrappers
            export MPICC="{mpicc}"
            export MPICXX="{mpicxx}"
            export MPIF90="{mpif90}"

            # allow the the compilers to be overrriden
            if [ "$ATDM_CONFIG_OVERRIDE_MPICXX" != "" ]; then
              export MPICXX="$ATDM_CONFIG_OVERRIDE_MPICXX"
            fi
            if [ "$ATDM_CONFIG_OVERRIDE_MPICXX_INNER_COMPILER" != "" ]; then
              export OMPI_CXX="$ATDM_CONFIG_OVERRIDE_MPICXX_INNER_COMPILER"
              export MPICH_CXX="$ATDM_CONFIG_OVERRIDE_MPICXX_INNER_COMPILER"
            fi

            echo "MPICXX=$MPICXX"
            echo "MPICH_CXX=$MPICH_CXX"

            export ATDM_CONFIG_MPI_EXEC="{mpiexec}"

            export ATDM_CONFIG_MPI_POST_FLAGS="{mpiexec_flags}"
            export ATDM_CONFIG_MPI_EXEC_NUMPROCS_FLAG="{mpiexec_np}"


            export ATDM_CONFIG_KNOWN_SYSTEM_NAME="{spack_magic}"
            export ATDM_CONFIG_GET_CUSTOM_SYSTEM_INFO_COMPLETED="1"
            export ATDM_CONFIG_SYSTEM_NAME="{spack_magic}"
            export ATDM_CONFIG_BUILD_TYPE="{atdm_config_build_type}"
            export ATDM_CONFIG_JOB_NAME="{atdm_config_build_name}"
            export ATDM_CONFIG_PT_PACKAGES="ON"
            export ATDM_CONFIG_CUSTOM_COMPILER_SET="1"
            export ATDM_CONFIG_COMPILER="{atdm_config_compiler}"
            export ATDM_CONFIG_CUSTOM_CONFIG_DIR="{spack_magic_dir}"
            export ATDM_CONFIG_CUSTOM_CONFIG_DIR_ARG="{spack_magic_dir}"
            export ATDM_CONFIG_SYSTEM_DIR="{spack_magic_dir}"
            export ATDM_CONFIG_BUILD_NAME="{atdm_config_build_name}"
            export ATDM_CONFIG_TRILINOS_DIR="{atdm_config_trilinos_dir}"
            export ATDM_CONFIG_FINISHED_SET_BUILD_OPTIONS="1"
            export ATDM_CONFIG_NODE_TYPE="{kokkos_node_type}"
            export ATDM_CONFIG_COMPLEX="{atdm_config_enable_complex}"
            export ATDM_CONFIG_SCRIPT_DIR="{atdm_config_trilinos_dir}/cmake/std/atdm"
            export ATDM_CONFIG_SHARED_LIBS="{atdm_config_build_shared_libs}"

            #export ATDM_CONFIG_Trilinos_LINK_SEARCH_START_STATIC=ON
            export ATDM_CONFIG_ADDRESS_SANITIZER=OFF
            export ATDM_CONFIG_USE_MPI=ON

            # this must be set
            export ATDM_CONFIG_COMPLETED_ENV_SETUP="TRUE"
        '''
        fmt = BlankFormatter()
        txt = fmt.format(txt,**config_map)
        env_lines.append(dedent(txt))

        return '\n'.join(env_lines)

    def _write_spack_magic_trilinos_env(self, spack_magic_dir):
        """
        Write out an en ENV script that load_env could eat
        Data is written to
                {spack_env_dir}/environment.sh
        """

        spack_env_file = '{0}/environment.sh'.format(spack_magic_dir)

        tty.msg("Writing ATDM 'environment'")
        tty.msg("Writing ATDM to: {0}".format(spack_env_file))

        with open(spack_env_file, "w") as fptr:
            fptr.write(self._create_spack_atdm_env())

    def _source_spack_magic_and_add_env(self, spack_env_dir, spack_env):

        command = ("bash -c 'source {0}/environment.sh && env'"
                   "".format(spack_env_dir))
        tty.msg('Sourcing fake ATDM env to get ENV diff...{0}'
                ''.format(command))

        command = shlex.split(command)

        proc = subprocess.Popen(command, stdout=subprocess.PIPE)
        for line in proc.stdout:
            (key, _, value) = line.decode().partition("=")
            value = value.strip()
            # should we add the var?
            add_value = False

            if re.match('^ATDM_.*$', key):
                add_value = True
            elif re.match('^(MPICC|MPICXX|MPI90|MPICH_CXX|OMPI_CXX)$', key):
                add_value = True
            elif re.match('^.*_ROOT$', key):
                tty.msg("=======++++++ ----- <<<< >>>>>> Found a Root {0}"
                        "".format(key))
                add_value = True

            if add_value:
                print("Got new ENV: {} = {}".format(key, value))
                os.environ[key] = value
        proc.communicate()

    def _get_true_name_version(self, spec_name):
        '''
        Determine the name and version of MPI.

        This attempts to uncover the real name of the MPI provider
        if it is provided using an external module.

        The logic isn't mensa level - it checks to see if
        {mpi_name} is contained with a module's name
        This isn't robust, but it seems to work given the
        current module setup on this machine.
        '''
        m = self.spec[spec_name].to_node_dict()
        for n, d in m.items():
            s_name = n
            s_version = d['version']
            if 'external' in d:
                if 'module' in d['external']:
                    for module in d['external']['module']:
                        # the real name of MPI is in the module name..
                        if n in module:
                            s_name, _, s_version = module.partition('/')
                            s_name = s_name.replace('_', '-')
        return s_name, s_version

    def _get_compiler_name_version(self):
        '''
            Ideally, I can resolve that the compiler is crayclang
            and in the future, maybe crayclang-amd
            e.g., if CC=crayclang and CXX=amd
            then we could lump together crayclang-11.0.3-amd-4.312.3
        '''
        compiler_name = self.compiler.name
        compiler_version = self.compiler.version
        return compiler_name, compiler_version

    @run_after('build')
    def check(self):
        timeout = ['--test-timeout 300', '--timeout 300']
        with working_dir(self.build_directory):
            opts = ['-j 8'] + timeout
            tty.debug("Preparing to run tests, -j 8 first")
            ctest(*opts, fail_on_error=False)
            tty.debug("Preparing to rerun-failed tests, -j 4 first")
            opts = ['--rerun-failed', '-j 4'] + timeout
            ctest(*opts, fail_on_error=False)
            tty.debug("Preparing to rerun-failed tests, -j 1 first")
            opts = ['-VV', '--rerun-failed', '-j 1'] + timeout
            # we'll fail if it does
            ctest(*opts)

    def _find_libraries(self,
                        dep_name,
                        shared=False,
                        query_map={},
                        override_libnames_map={}):
        spec = self.spec

        # fully qualified paths to the libraries
        libs = []
        inc_dirs = []
        lib_dirs = []
        libnames = []

        # restrict the spec if needed
        if dep_name in query_map:
            spec_query = query_map[dep_name]
            package_spec = spec[spec_query]
            # print(f"spec['{spec_query}']")
        else:
            package_spec = spec[dep_name]

        # pprint(package_spec.to_node_dict())
        # extract the libnames
        try:
            # print("spec.libs")
            # pprint(package_spec.libs)

            package_lib_names = package_spec.libs.names

            if dep_name in override_libnames_map:
                package_lib_names = override_libnames_map[dep_name]

            libnames = ['lib' + c for c in package_lib_names]

            # TODO - handle if these are lists or not?
            try:
                inc_dirs = [package_spec.prefix.include]
            except:
                pass
            try:
                lib_dirs = [package_spec.prefix.lib]
            except:
                pass

            # print('Got libs.names...')
            # pprint(libnames)
        except spack.error.NoLibrariesError:
            # give up if you get none
            return libs, inc_dirs, lib_dirs

        # quit if we got none
        if len(libnames) < 1:
            return libs, inc_dirs, lib_dirs

        txt = '''calling find_libraries(
                {names},
                root={root},
                shared={shared},
                recursive=True).split()
            '''
        txt = dedent(txt).format(names=libnames,
                                 root=package_spec.prefix,
                                 shared=shared)
        # pprint(txt)

        libs = str(find_libraries(libnames,
                                  root=package_spec.prefix,
                                  shared=shared,
                                  recursive=True)).split()
        # pprint(libs)

        # print("++++ Getting dependents...")
        for n in package_spec.dependencies_dict():
            # print('++++' + n)
            # pprint(package_spec[n].to_dict())
            # print("Calling new find libraries with {}".format(n))
            new_libs, new_inc_dirs, new_lib_dirs = self._find_libraries(n, shared)
            # print("Got new libs: {}".format(new_libs))
            libs += new_libs
            inc_dirs += new_inc_dirs
            lib_dirs += new_lib_dirs
        return libs, inc_dirs, lib_dirs

    def _gather_core_tpl_libraries(self,
                                   core_tpls,
                                   query_map={},
                                   override_libnames_map={},
                                   blacklist_static=[],
                                   shared=False,
                                   wrap_groups=False):
        from pathlib import Path

        banner = '*' * 80
        libs = {}
        inc_dirs = {}
        lib_dirs = {}
        for tpl in core_tpls:
            print(banner)
            print("Calling new find libraries")
            libs[tpl] = []
            inc_dirs[tpl] = []
            lib_dirs[tpl] = []

            libs[tpl], inc_dirs[tpl], lib_dirs[tpl] = \
                self._find_libraries(tpl,
                                     shared=shared,
                                     query_map=query_map,
                                     override_libnames_map=override_libnames_map)
            # remove duplicate - this is OKAY if you are use a groups
            inc_dirs[tpl] = list(dict.fromkeys(inc_dirs[tpl]))
            lib_dirs[tpl] = list(dict.fromkeys(lib_dirs[tpl]))

            if wrap_groups and len(libs[tpl]) > 1:
                libs[tpl] = list(dict.fromkeys(libs[tpl]))
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
                new_libs = []
                for l in libs[tpl]:
                    for blacklisted in blacklist_static:
                        if blacklisted in l:
                            libname = Path(l).name
                            m = re.match(r'^lib(?P<name>.*)\.a', libname)
                            if m:
                                new_l = m.group('name')
                                # prefix the library with the search path... I guess we
                                # could swap to .so and hope for the best?
                                new_l_pref = ['-L{0}'.format(d) for d in lib_dirs[tpl]]
                                new_l = f'-l{new_l}'
                                tty.msg(f"{l} => {new_l}")
                                new_libs += new_l_pref + [new_l]
                            else:
                                tty.msg('WTF: matched {0}, but failed to match lib{1}.a'
                                        ''.format(blacklisted, libname))
                                tty.msg(f'   : lib = {l}')
                                new_libs.append(l)

                libs[tpl] = new_libs

            print("libs = {}".format(libs[tpl]))
            print("inc_dirs = {}".format(inc_dirs[tpl]))
            print("lib_dirs = {}".format(lib_dirs[tpl]))

        print(banner)

        return libs, inc_dirs, lib_dirs
