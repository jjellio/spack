# Copyright 2013-2021 Lawrence Livermore National Security, LLC and other
# Spack Project Developers. See the top-level COPYRIGHT file for details.
#
# SPDX-License-Identifier: (Apache-2.0 OR MIT)

import os
import sys
from textwrap import dedent
from spack import *
from spack.operating_systems.mac_os import macos_version
from spack.pkg.builtin.kokkos import Kokkos
import llnl.util.tty as tty
from pprint import pprint
import os
import re
import shlex
import subprocess

class AtdmTrilinos(CMakePackage, CudaPackage, ROCmPackage):
	"""The Trilinos Project is an effort to develop algorithms and enabling
	technologies within an object-oriented software framework for the solution
	of large-scale, complex multi-physics engineering and scientific problems.
	A unique design feature of Trilinos is its focus on packages.
	"""
	homepage = "https://trilinos.org/"
	git		 = "https://github.com/trilinos/Trilinos.git"

	maintainers = ['keitat']

	# ###################### Versions ##########################

	version('develop', branch='develop', preferred=True)
	version('master', branch='master')
	version('13.0.1',
			sha256='0bce7066c27e83085bc189bf524e535e5225636c9ee4b16291a38849d6c2216d')

	# ###################### Variants ##########################
	##	netcdf-c:
	##		variants: ~hdf4~jna+mpi+parallel-netcdf+dap+pic+shared build_type=RelWithDebInfo
	##	parallel-netcdf:
	##		variants: ~cxx~burstbuffer+fortran+pic+shared
	##	cgns:
	##		variants: ~base_scope~int64~ipo~legacy~mem_debug~fortran+hdf5+mpi+parallel+scoping+static+ninja  build_type=RelWithDebInfo
	##	hdf5:
	##		variants: ~cxx~debug~threadsafe~java+fortran+hl+mpi+pic+shared+szip build_type=RelWithDebInfo
	##		version:	[ 1.10.7 ]
	##	boost:
	##		variants: +shared+pic+system+icu cxxstd=11 build_type=RelWithDebInfo
	##	superlu-dist:
	##		variants:  ~cuda~ipo~int64+shared ^cray-libsci ~mpi+shared	build_type=RelWithDebInfo
	##				# ~cuda~ipo~int64+openmp+shared ^cray-libsci ~mpi+openmp+shared
	##				# ~cuda~ipo~int64~openmp+shared ^cray-libsci ~mpi~openmp+shared
	##	parmetis:
	##		variants: ~gdb~ipo~int64+ninja+shared  build_type=RelWithDebInfo
	##	metis:
	##		variants: ~gdb+real64~int64+shared	build_type=RelWithDebInfo
	variant('complex', default=False)

	variant('ci_hostname',
			multi=False,
			default='redwood')

	variant('sparc',	default=False,
			description='Enable the packages SPARC uses')
	variant('empire', default=True,
			description='Enable the packages EMPIRE uses')

	variant('shared', default=True)

	variant('exec_space', default='serial',
			values=('serial',
				'openmp',
				'cuda',
				'rocm'),
			description='the execution space to build')

	variant('host_lapack', default='libsci',
			values=('libsci','openblas'),
			description='the host blas/lapack to use')

	variant('ninja', default=True, description='Uses Ninja build system')
	variant('trace_cmake', default=False,
			description='-traces cmake, produces substantial output '\
					'- for debugging cmake issues only')

	# adding this is causing a the package to depend on the default libsci spec
	# which will the conflict the exec_space=openmp variant
	#depends_on('blas',
	#		type=('build', 'link', 'run'))
	#depends_on('lapack',
	#		type=('build', 'link', 'run'))
	depends_on('mpi',
			type=('build', 'link', 'run'))

	depends_on('cmake@3.19:')
	depends_on('ninja@kitware', when='+ninja')

	# I think this needs to be early... before any child can require it
	# exec_space=openmp host_lapack=libsci

	depends_on('cray-libsci~mpi+shared+openmp',
			type=('build', 'link', 'run'),
			when='host_lapack=libsci exec_space=openmp')

	depends_on('cray-libsci~mpi+shared~openmp',
			type=('build', 'link', 'run'),
			when='exec_space=serial host_lapack=libsci')

	print('hdf5@1.10.7~cxx~debug~threadsafe~java+fortran+hl+mpi+pic+shared+szip');
	depends_on('hdf5@1.10.7~cxx~debug~threadsafe~java+fortran+hl+mpi+pic+shared+szip',
			type=('build', 'link', 'run'),
			)
	print('netcdf-c@4.7.0:4.7.99~hdf4~jna+mpi+parallel-netcdf+dap+pic+shared');
	depends_on('netcdf-c@4.7.0:4.7.99~hdf4~jna+mpi+parallel-netcdf+dap+pic+shared',
			type=('build', 'link', 'run'),
			)
	print('parallel-netcdf~cxx~burstbuffer+fortran+pic+shared');
	depends_on('parallel-netcdf~cxx~burstbuffer+fortran+pic+shared',
			type=('build', 'link', 'run'),
			)
	print('parmetis@4.0.3~gdb~ipo~int64+ninja+shared');
	depends_on('parmetis@4.0.3~gdb~ipo~int64+ninja+shared',
			type=('build', 'link', 'run'),
			)
	print('metis@5:~gdb+real64~int64~shared');
	depends_on('metis@5:~gdb+real64~int64~shared',
			type=('build', 'link', 'run'),
			)
	print('cgns~base_scope~int64~ipo~legacy~mem_debug~fortran+hdf5+mpi+parallel+scoping+static+ninja');
	depends_on('cgns~base_scope~int64~ipo~legacy~mem_debug~fortran+hdf5+mpi+parallel+scoping+static+ninja',
			type=('build', 'link', 'run'),
			)

	print('superlu-dist@6.4.0~ipo~int64+shared')
	depends_on('superlu-dist@6.4.0~ipo~int64+shared+openmp^cray-libsci+openmp',
			type=('build', 'link', 'run'),
			when='exec_space=openmp host_lapack=libsci')

	depends_on('superlu-dist@6.4.0~ipo~int64+shared~openmp',
			type=('build', 'link', 'run'),
			when='exec_space=serial')

	print('boost+shared+pic+system+icu cxxstd=11');
	depends_on('boost+shared+pic+system+icu cxxstd=11',
			type=('build', 'link', 'run'),
			)

	depends_on('python@3:', type=('build', 'link', 'run'))

	depends_on('rocm',
			type=('build', 'link', 'run'),
			when='exec_space=rocm')

	depends_on('cuda',
			type=('build', 'link', 'run'),
			when='exec_space=cuda')

	print("done")


	def url_for_version(self, version):
		try:
			print('self.compiler')
			pprint(self.compiler)
			print('self.compiler.to_dict()')
			pprint(self.compiler.to_dict())
		except:
			pass

		try:
			print('self.compiler.modules')
			pprint(self.compiler.modules)
			print('self.compiler.modules.to_dict')
			pprint(self.compiler.modules.to_dict())
		except:
			pass
		try:
			print('self.compiler.cxx')
			pprint(self.compiler.cxx)
			print('self.compiler.cxx.to_dict')
			pprint(self.compiler.cxx.to_dict())
		except:
			pass
		url = "https://github.com/trilinos/Trilinos/archive/trilinos-release-{0}.tar.gz"
		return url.format(version.dashed)

	def cmake_args(self):
		spec = self.spec
		options = []
		define = CMakePackage.define

		#import traceback
		#traceback.print_stack()

		trilinos_option_file='cmake/std/atdm/ATDMDevEnv.cmake'
		if '+empire' in spec:
			trilinos_option_file+=';cmake/std/atdm/apps/empire/EMPIRETrilinosEnables.cmake'
		if '+sparc' in spec:
			trilinos_option_file+=';cmake/std/atdm/apps/sparc/SPARCTrilinosEnables.cmake'

		if '+trace_cmake' in spec:
			options +=['--trace-expand']
		options.extend([
			define('Trilinos_ENABLE_TESTS', True),
			define('Trilinos_ENABLE_EXAMPLES', True),
			#define('Trilinos_ENABLE_ALL_OPTIONAL_PACKAGES', True),
			#define('Trilinos_WARNINGS_AS_ERRORS_FLAGS', ''),
			#define('Trilinos_ALLOW_NO_PACKAGES', True),
			#define('Trilinos_DISABLE_ENABLED_FORWARD_DEP_PACKAGES', True),
			#define('Trilinos_DEPS_XML_OUTPUT_FILE', ''),
			#define('Trilinos_ENABLE_SECONDARY_TESTED_CODE', True),
			#define('Trilinos_EXTRAREPOS_FILE', ''),
			#define('Trilinos_IGNORE_MISSING_EXTRA_REPOSITORIES', True),
			#define('Trilinos_ENABLE_KNOWN_EXTERNAL_REPOS_TYPE', 'None'),
			#define('Trilinos_ENABLE_ALL_PACKAGES', True),
			define('Trilinos_TRACE_ADD_TEST', True),
			define('Trilinos_ENABLE_CONFIGURE_TIMING', True),
			define('Trilinos_HOSTNAME', spec.variants['ci_hostname'].value),
			define('Trilinos_CONFIGURE_OPTIONS_FILE', trilinos_option_file),
			])

		# ################## Trilinos Packages #####################
		# we want to 'source' 


		#blas = spec['blas'].libs
		#lapack = spec['lapack'].libs
		#options.extend([
		#	 define('TPL_ENABLE_BLAS', True),
		#	 define('BLAS_LIBRARY_NAMES', blas.names),
		#	 define('BLAS_LIBRARY_DIRS', blas.directories),
		#	 define('TPL_ENABLE_LAPACK', True),
		#	 define('LAPACK_LIBRARY_NAMES', lapack.names),
		#	 define('LAPACK_LIBRARY_DIRS', lapack.directories),
		#])

		return options

	@property
	def std_cmake_args(self):
		"""This allows the Ninja generator to be set based on the spec
		:return: standard cmake arguments
		"""
		# standard CMake arguments
		if "+ninja" in self.spec:
			CMakePackage.generator="Ninja"

		std_cmake_args = CMakePackage._std_args(self)

		#std_cmake_args += getattr(self, 'cmake_flag_args', [])
		return std_cmake_args

	def cmake(self, spec, prefix):
		print("++++========== ////	||||	 \\\\\\\\ ================== ++++++")
		print(" Calling cmake hook:")
		print("Current ATDM_CONFIG_COMPLETED_ENV_SETUP = {}".format(os.environ.get('ATDM_CONFIG_COMPLETED_ENV_SETUP', 'unset')))

		# atdm config source location
		trilinos_src=self.stage.source_path
		os.system("ls -l {}".format(trilinos_src))

		tty.msg("ATDM_CONFIG_CUSTOM_CONFIG_DIR = {}".format(os.environ.get('ATDM_CONFIG_CUSTOM_CONFIG_DIR', 'unset')))
		if 'ATDM_CONFIG_CUSTOM_CONFIG_DIR' in os.environ:
			spack_env_dir=os.environ['ATDM_CONFIG_CUSTOM_CONFIG_DIR']
			os.system(f'cp -vr {spack_env_dir} {trilinos_src}/cmake/std/atdm/')
			os.system(f"ls -l {trilinos_src}/cmake/std/atdm/")
		#self._write_spack_magic('spack_magic')

		# RelWithDebInfo | Release | Debug
		# be careful here... Trilinos release-debug enables bound checking in kokkos
		# we are probably best using release in Trilinos + -g
		#print("build_type = {}".format(self.spec.variants['build_type'].value))

		# we want to 'source' an ENV script with the proper build tokens
		# then capture the ENV changes between then vs now. (should be
		# abunch of ATDM_ prefixed variables)
		# we then set those vars in SPACK's build ENV
		# but set the values for TPLs to match SPACKs
		#
		# optionally, write out a suitable ENV in return that could be used after the build
		# to load-matching-env.sh
		#pprint(spec.to_dict())
		#pprint(self.__dict__)
		#pprint(self.stage.__dict__)
		#pprint(self.stage.source_path)

		#self._source_build_id_and_add_env('spack_magic')
		#command = shlex.split("bash -c 'env | grep ^ATDM'")
		#proc = subprocess.Popen(command, stdout = subprocess.PIPE)
		#for line in proc.stdout:
		#	print(line)
		#proc.communicate()

		super(AtdmTrilinos, self).cmake(spec,prefix)

	def setup_build_environment(self, spack_env):
		tty.msg("Preparing ATDM environment in setup_build_environment")
		spack_env_dir = self._write_spack_magic()
		self._source_spack_magic_and_add_env(spack_env_dir,spack_env)

	def _write_spack_magic(self, spack_magic_name='spack_magic'):
		tty.msg("Generating ATDM config environment called {}".format(spack_magic_name))

		# write into Trilinos_src/cmake/std/atdm (we don't technically need to)
		# trilinos doesn't exists yet.. so make it in cwd()
		spack_env_dir=f'{os.getcwd()}/spack_magic'
		#spack_env_dir='{}/cmake/std/atdm/{}'.format(self.stage.source_path,spack_magic_name)
		tty.msg(f"Generating ATDM config, creating directory: {spack_env_dir}")
		try:
			os.mkdir(spack_env_dir)
		except FileExistsError:
			pass

		self._write_spack_magic_trilinos_env(spack_env_dir)
		self._write_spack_magic_custom_builds(spack_env_dir)

		spack_env_file=f'{spack_env_dir}/environment.sh'
		os.system("ls -l {}".format(spack_env_dir))
		os.system("echo {}".format(spack_env_file))
		os.system("cat {}".format(spack_env_file))

		return spack_env_dir

	def _get_atdm_compiler_config_name(self):
		"""
		This is not strictly necessary, but this allows us to express a 'config name'
		for the recipe we are about to build.  By default, Trilinos uses some well defined
		names that map directly to CDash dashboards.

		For now we want to capture things like accelerator, compiler, and MPI names/versions

		Data is written to
			{spack_env_dir}/custom_builds.sh
			export ATDM_CONFIG_COMPILER={compiler_name}-{compiler_version}_{mpi_name}-{mpi_version}[-{more}...]
		"""
		compiler_name,compiler_version = self._get_compiler_name_version()
		atdm_config_name=f'{compiler_name}-{compiler_version}'
		if 'exec_space=rocm' in self.spec:
			rocm_name,rocm_version = self._get_true_name_version('rocm')
			atdm_config_name+=f'_{rocm_name}-{rocm_version}'
		elif 'exec_space=openmp' in self.spec:
			atdm_config_name+='_openmp'

		mpi_name,mpi_version = self._get_true_name_version('mpi')
		atdm_config_name+=f'_{mpi_name}-{mpi_version}'

		return atdm_config_name

	def _write_spack_magic_custom_builds(self, spack_magic_dir):
		"""
		This is not strictly necessary, but this allows us to express a 'config name'
		for the recipe we are about to build.  By default, Trilinos uses some well defined
		names that map directly to CDash dashboards.

		For now we want to capture things like accelerator, compiler, and MPI names/versions

		Data is written to
			{spack_env_dir}/custom_builds.sh
			export ATDM_CONFIG_COMPILER={compiler_name}-{compiler_version}_{mpi_name}-{mpi_version}[-{more}...]
		"""

		atdm_config_name = self._get_atdm_compiler_config_name()

		template=f"""
		# write to spack_env_dir/custom_builds.sh
		export ATDM_CONFIG_COMPILER="{atdm_config_name}"
		"""

		tty.msg("Writing ATDM config custom_builds.sh")
		tty.msg(f"Chose ATDM_CONFIG_COMPILER={atdm_config_name}")

		spack_compiler_file=f'{spack_magic_dir}/custom_builds.sh'
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

			ATDM_SET_CACHE(TPL_BLAS_LIBRARIES "$ENV{ATDM_CONFIG_BLAS_LIBS}" CACHE FILEPATH)
			ATDM_SET_CACHE(TPL_LAPACK_LIBRARIES "$ENV{ATDM_CONFIG_LAPACK_LIBS}" CACHE FILEPATH)

			#
			# maybe best to ignore boost... they hardcode the paths as-is
			#
			ATDM_SET_CACHE(TPL_Boost_LIBRARIES
			   "$ENV{BOOST_ROOT}/lib/libboost_program_options.${ATDM_TPL_LIB_EXT};$ENV{BOOST_ROOT}/lib/libboost_system.${ATDM_TPL_LIB_EXT}"
			  CACHE FILEPATH)

			# BoostLib
			IF (NOT "$ENV{ATDM_CONFIG_BOOST_LIBS}" STREQUAL "")
			  ATDM_SET_CACHE(TPL_BoostLib_LIBRARIES "$ENV{ATDM_CONFIG_BOOST_LIBS}" CACHE FILEPATH)
			ELSE()
			  ATDM_SET_CACHE(TPL_BoostLib_LIBRARIES
			    "$ENV{BOOST_ROOT}/lib/libboost_program_options.${ATDM_TPL_LIB_EXT};$ENV{BOOST_ROOT}/lib/libboost_system.${ATDM_TPL_LIB_EXT}"
			    CACHE FILEPATH)
			ENDIF()

			# METIS
			ATDM_SET_CACHE(TPL_METIS_LIBRARIES "$ENV{ATDM_CONFIG_METIS_LIBS}" CACHE FILEPATH)

			# ParMETIS
			ATDM_SET_CACHE(TPL_ParMETIS_LIBRARIES "$ENV{ATDM_CONFIG_PARMETIS_LIBS}" CACHE FILEPATH)


			# CGNS
			IF (NOT "$ENV{ATDM_CONFIG_CGNS_LIBRARY_NAMES}" STREQUAL "")
			  ATDM_SET_CACHE(CGNS_LIBRARY_NAMES "$ENV{ATDM_CONFIG_CGNS_LIBRARY_NAMES}" CACHE FILEPATH)
			ENDIF()
			ATDM_SET_CACHE(TPL_CGNS_LIBRARIES "$ENV{ATDM_CONFIG_CGNS_LIBS}" CACHE FILEPATH)

			# HDF5
			  ATDM_SET_CACHE(TPL_HDF5_LIBRARIES "$ENV{ATDM_CONFIG_HDF5_LIBS}" CACHE FILEPATH)

			# Netcdf
			    ATDM_SET_CACHE(TPL_Netcdf_LIBRARIES "$ENV{ATDM_CONFIG_NETCDF_LIBS}" CACHE FILEPATH)

			# SuperLUDist
			ATDM_SET_CACHE(SuperLUDist_INCLUDE_DIRS "$ENV{ATDM_CONFIG_SUPERLUDIST_INCLUDE_DIRS}" CACHE FILEPATH)
			ATDM_SET_CACHE(TPL_SuperLUDist_LIBRARIES "$ENV{ATDM_CONFIG_SUPERLUDIST_LIBS}" CACHE FILEPATH)

			# many inconsistencies here
			SuperLUDist doens't work using ROOT for includes
			Boost doesn't use libraries but boostlib does
		'''

		core_tpls = {
				'hdf5'						: 'HDF5',
				'netcdf-c'				: 'NETCDF',
				'parallel-netcdf'	: 'PNETCDF',
				'boost'						:	'BOOST',
				'cgns'						:	'CGNS',
				'metis'						:	'METIS',
				'parmetis'				:	'PARMETIS',
				'superlu-dist'		:	'SUPERLUDIST',
				'blas'						:	'BLAS',
				'lapack'					:	'LAPACK' }

		libs_required_shared = [
				'libsci' ]
		# this is an expensive call
		# returns a map of spack dependencies and their libraries
		# if shared=False, then we should use them as-is
		# if we instead want -L/path -lfoo -lbar
		# then we we should loop through each list of libraries
		# and compute the directories and libnames
		tpl_libs,tpl_incs,tpl_libdirs=self._gather_core_tpl_libraries(
																							shared=False,
																							wrap_groups=True,
																							required_shared=libs_required_shared,
																							core_tpls=core_tpls.keys())

		env_lines = []
		txt='''
			# This is an auto-generated file used to mimic the 'source -> configure -> build'
			# method used by some Trilinos workflows
			echo "Inside fake env"
			'''
		env_lines.append(dedent(txt))

		# setup our variables
		# ideally we'd like to module load tpl-exec_space, and have it do
		# all of this. Currently, spack's module naming isn't making the required modules
		# alternatively, we could maybe add a meta-moduled, atdm-dev-exec_space... this
		# would all look much better
		for spec_name,atdm_name in core_tpls.items():
			prefix=self.spec[spec_name].prefix
			# cmake wants semicolon delimited lists
			inc_dirs=';'.join(tpl_incs[spec_name])
			libs=';'.join(tpl_libs[spec_name])

			#lib_dirs... would need to do something..
			#lib_names... I wouldn't set this, set libs to -Ldirs;libnames
			txt=f'''
			_spack_{atdm_name}_ROOT="{prefix}"
			: "${{{atdm_name}_ROOT:=${{_spack_{atdm_name}_ROOT}}}}"
			unset _spack_{atdm_name}_ROOT
			export {atdm_name}_ROOT

			export ATDM_CONFIG_{atdm_name}_INCLUDE_DIRS="{inc_dirs}"
			export ATDM_CONFIG_{atdm_name}_LIBS="{libs}"
			'''
			env_lines.append(dedent(txt))

		# this sucks - Cray provides bin utils for all CCE, but spack can't understand that
		# ideally, you could make a package that is aware that it is controlled by the compiler module
		# but if you module load CCE in that package you are hosed
		#
		# I don't know what you are supposed to do..
		txt='''

			# yuck
			export BINUTILS_ROOT={bin_utils_root}
			# leaving this off for now... this could be evil
			export ATDM_CONFIG_BINUTILS_LIBS="-L${{BINUTILS_ROOT}}/lib;-lbfd"
			'''.format(bin_utils_root=os.environ.get('CRAY_BINUTILS_ROOT',''))

		env_lines.append(dedent(txt))

		# we've handled libraries, now do the compilers
		# self.compilers.modules contains the loaded compiler modules
		compiler_modules = dict.fromkeys(self.compiler.modules)

		# there is a LLNL module for querying micro arch...
		# but we want to use whatever we are targetting via Cray
		# spack should really provide support for module based microarch
		# compiling. e.g., craype-x86-haswell
		if 'CRAY_CPU_TARGET' in os.environ:
			micro_arch_map = {
					'x86-naples'	: 'ZEN',
					'x86-rome'		: 'ZEN2',
					'x86-milan'		: 'ZEN3'
					}
			# this will throw if the ENV isn't set... so spack better be nice
			# with cray!
			kokkos_arch=micro_arch_map[os.environ['CRAY_CPU_TARGET']]
			tty.msg(f"Setting Kokkos_ARCH using CrayPE ... got {kokkos_arch}")
		else:
			kokkos_arch=Kokkos.spack_micro_arch_map[self.spec.target.name].upper()
			tty.msg(f"Setting Kokkos_ARCH using spec.target.name ... got {kokkos_arch}")

		# handle GPU stuff... todo
		# the Cmake stuff will handle turning on exec spaces
		# done via load-env.sh foo-openmp|cuda|serial-stuff
		# we usually specify the kokkos arch in the env script
		txt=f'''
			export ATDM_CONFIG_KOKKOS_ARCH="{kokkos_arch}"
			'''
		env_lines.append(dedent(txt))


		ci_hostname=self.spec.variants['ci_hostname'].value
		mpiexec_flags='--cpu-bind=cores;-c;1'
		mpiexec_np='-n'
		# need to fix this
		mpiexec='srun'
		mpicc = self.compiler.cc
		mpicxx = self.compiler.cxx
		mpif90 = self.compiler.fc

		spack_magic='spack_magic'
		spack_magic_dir=f'{self.stage.source_path}/cmake/std/atdm/{spack_magic}'
		kokkos_node_type=str(self.spec.variants['exec_space'].value).lower()

		atdm_config_build_type=self.spec.variants['build_type'].value.lower()
		# this is the weird name from custom-builds.sh
		atdm_config_compiler=self._get_atdm_compiler_config_name()
		# this is the 'build name' givin to load-env
		atdm_config_build_name=f'{spack_magic}-{atdm_config_compiler}-{atdm_config_build_type.lower()}-{kokkos_node_type.lower()}'

		# if we were guaranteed python3.6+ we could do {atdm_config_build_type.upper()}
		kokkos_node_type=kokkos_node_type
		atdm_config_build_type=atdm_config_build_type

		if self.spec.variants['complex'].value:
			atdm_config_enable_complex='ON'
			atdm_config_build_name+='-complex'
		else:
			atdm_config_enable_complex='OFF'

		if self.spec.variants['shared'].value:
			atdm_config_build_name+='-shared'
			atdm_config_build_shared_libs='ON'
		else:
			atdm_config_build_shared_libs='OFF'

		txt=f'''
			# this is an internal variable that enables the libraries common to both
			# sparc and empire ... it's name predates empire using it
			export ATDM_CONFIG_ENABLE_SPARC_SETTINGS=ON

			# override the hostnames used... hopefully this helps cdash work
			export ATDM_CONFIG_KNOWN_HOSTNAME={ci_hostname}
			export ATDM_CONFIG_CDASH_HOSTNAME={ci_hostname}
			export ATDM_CONFIG_REAL_HOSTNAME={ci_hostname}

			# this doesn't do anything outside test scripts
			export ATDM_CONFIG_USE_NINJA=ON

			#Not sure if we need these... they may get auto set
			# they are set in ats2
			# ATDM Settings
			export ATDM_CONFIG_CUDA_RDC="OFF"
			export ATDM_CONFIG_USE_CUDA=OFF
			export ATDM_CONFIG_USE_OPENMP=OFF
			export ATDM_CONFIG_USE_PTHREADS=OFF
			export ATDM_CONFIG_CTEST_PARALLEL_LEVEL=4
			export ATDM_CONFIG_BUILD_COUNT=60
			export ATDM_CONFIG_FPIC="OFF"

			# Kokkos Settings
			export ATDM_CONFIG_Kokkos_ENABLE_SERIAL=ON
			#export KOKKOS_NUM_DEVICES=4

			# Set common MPI wrappers
			export MPICC="{mpicc}"
			export MPICXX="{mpicxx}"
			export MPIF90="{mpif90}"

			export ATDM_CONFIG_MPI_EXEC="{mpiexec}"

			export ATDM_CONFIG_MPI_POST_FLAGS="{mpiexec_flags}"
			export ATDM_CONFIG_MPI_EXEC_NUMPROCS_FLAG="{mpiexec_np}"


			export ATDM_CONFIG_KNOWN_SYSTEM_NAME="{spack_magic}"
			export ATDM_CONFIG_GET_CUSTOM_SYSTEM_INFO_COMPLETED="1"
			export ATDM_CONFIG_SYSTEM_NAME="{spack_magic}"
			export ATDM_CONFIG_BUILD_TYPE="{atdm_config_build_type.upper()}"
			export ATDM_CONFIG_JOB_NAME="{atdm_config_build_name}"
			export ATDM_CONFIG_PT_PACKAGES="OFF"
			export ATDM_CONFIG_CUSTOM_COMPILER_SET="1"
			export ATDM_CONFIG_COMPILER="{atdm_config_compiler}"
			export ATDM_CONFIG_CUSTOM_CONFIG_DIR="{spack_magic_dir}"
			export ATDM_CONFIG_CUSTOM_CONFIG_DIR_ARG="{spack_magic_dir}"
			export ATDM_CONFIG_SYSTEM_DIR="{spack_magic_dir}"
			export ATDM_CONFIG_BUILD_NAME="{atdm_config_build_name}"
			export ATDM_CONFIG_TRILINOS_DIR="{self.stage.source_path}"
			export ATDM_CONFIG_FINISHED_SET_BUILD_OPTIONS="1"
			export ATDM_CONFIG_NODE_TYPE="{kokkos_node_type.upper()}"
			export ATDM_CONFIG_COMPLEX="{atdm_config_enable_complex}"
			export ATDM_CONFIG_SCRIPT_DIR="{self.stage.source_path}/cmake/std/atdm"
			export ATDM_CONFIG_SHARED_LIBS="{atdm_config_build_shared_libs}"

			#export ATDM_CONFIG_Trilinos_LINK_SEARCH_START_STATIC=ON
			export ATDM_CONFIG_ADDRESS_SANITIZER=OFF
			export ATDM_CONFIG_USE_MPI=ON

			# this must be set
			export ATDM_CONFIG_COMPLETED_ENV_SETUP="TRUE"
		'''
		env_lines.append(dedent(txt))

		return '\n'.join(env_lines)


	def _write_spack_magic_trilinos_env(self, spack_magic_dir):
		"""
		Write out an en ENV script that load_env could eat
		Data is written to
			{spack_env_dir}/environment.sh
		"""

		spack_env_file=f'{spack_magic_dir}/environment.sh'

		tty.msg("Writing ATDM 'environment'")
		tty.msg(f"Writing ATDM to: {spack_env_file}")

		with open(spack_env_file, "w") as fptr:
			fptr.write(self._create_spack_atdm_env())

	def _source_spack_magic_and_add_env(self, spack_env_dir, spack_env):

		env_new  = {}
		command = f"bash -c 'source {spack_env_dir}/environment.sh && env'"
		tty.msg('Sourcing fake ATDM env to get ENV diff...{command}')

		command = shlex.split(command)

		proc = subprocess.Popen(command, stdout = subprocess.PIPE)
		for line in proc.stdout:
			(key, _, value) = line.decode().partition("=")
			value=value.strip()
			# should we add the var?
			add_value = False

			if re.match('^ATDM_.*$',key):
				add_value=True
			elif re.match('^(MPICC|MPICXX|MPIFC)$',key):
				add_value=True
			elif re.match('^.*_ROOT$',key):
				tty.msg(f"=======++++++ ----- <<<< >>>>>> Found a Root {key}")
				add_value=True

			if add_value:
				print("Got new ENV: {} = {}".format(key,value))
				os.environ[key] = value
		proc.communicate()

	def _get_true_name_version(self,spec_name):
		'''
		Determine the name and version of MPI.

		This attempts to uncover the real name of the MPI provider
		if it is provided using an external module.

		The logic isn't mensa level - it checks to see if
		{mpi_name} is contained with a module's name
		This isn't robust, but it seems to work given the
		current module setup on this machine.
		'''
		m=self.spec[spec_name].to_node_dict()
		for n,d in m.items():
			s_name = n
			s_version = d['version']
			if 'external' in d:
				if 'module' in d['external']:
					for module in d['external']['module']:
						# the real name of MPI is in the module name..
						if n in module:
							s_name,_,s_version = module.partition('/')
							s_name = s_name.replace('_','-')
		return s_name,s_version

	def _get_compiler_name_version(self):
		'''
			Ideally, I can resolve that the compiler is crayclang
			and in the future, maybe crayclang-amd
			e.g., if CC=crayclang and CXX=amd
			then we could lump together crayclang-11.0.3-amd-4.312.3
		'''
		compiler_name = self.compiler.name
		compiler_version = self.compiler.version
		return compiler_name,compiler_version

	def _find_libraries(self,
											dep_name,
											shared=False,
											required_shared=[]):
		spec = self.spec

		banner='*'*80
		# fully qualified paths to the libraries
		libs = []
		inc_dirs = []
		lib_dirs = []
		libnames = []
		query_map = {
				'hdf5' : 'hdf5:hl,fortran',
				'boost' : 'boost:system,program_options'
				}

		override_libnames = {
				'boost' : ['boost_system','boost_program_options']
				}

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

			if dep_name in override_libnames:
				package_lib_names = override_libnames[dep_name]

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

		libs = str(find_libraries(
        libnames,
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

			libs[tpl],inc_dirs[tpl],lib_dirs[tpl] = self._find_libraries(tpl,shared=shared,required_shared=required_shared)
			# remove duplicate - this is OKAY if you are use a groups
			inc_dirs[tpl] = list(dict.fromkeys( inc_dirs[tpl] ))
			lib_dirs[tpl] = list(dict.fromkeys( lib_dirs[tpl] ))

			if wrap_groups and len(libs[tpl]) > 1:
				libs[tpl] = list(dict.fromkeys( libs[tpl] ))
				libs[tpl] = ['-Wl,--start-group'] + libs[tpl] + ['-Wl,--end-group']
			# I'd like to handle static/shared better
			# cray requires atleast libsci to be dynamic
			need_fix = False
			for l in libs[tpl]:
				if 'sci_cray' in l:
					need_fix = True

			if need_fix:
				tty.msg(f"Adjusting TPL: {tpl} Making all sci_cray libraries shared if they are static")
				new_l_prefix = ';'.join([ f'-L{d}' for d in lib_dirs[tpl] ])
				new_libs = []
				for l in libs[tpl]:
					if 'sci_cray' in l:
						libname = Path(l).name
						m = re.match('^lib(?P<name>.*)\.a', libname)
						if m:
							new_l = m.group('name')
							new_l = f'{new_l_prefix};-l{new_l}'
							tty.msg(f"{l} => {new_l}")
							new_libs.append(new_l)
						else:
							tty.msg('WTF: matched sci_cray, but failed to match foo.a')
							tty.msg(f'   : lib = {l}')
							new_libs.append(l)
					else:
						new_libs.append(l)

				libs[tpl] = new_libs

			print("libs = {}".format(libs[tpl]))
			print("inc_dirs = {}".format(inc_dirs[tpl]))
			print("lib_dirs = {}".format(lib_dirs[tpl]))

		print(banner)



		return libs,inc_dirs,lib_dirs
