# Copyright 2013-2021 Lawrence Livermore National Security, LLC and other
# Spack Project Developers. See the top-level COPYRIGHT file for details.
#
# SPDX-License-Identifier: (Apache-2.0 OR MIT)
from spack import *


class CrayPeTargets(Package):
    ''' Loads craype-foo modules
    '''
    homepage = "https://docs.nersc.gov/development/libraries/libsci/"
    has_code = False    # Skip attempts to fetch source that is not available

    version("all")

    variant("craype-host",
            values=("naples", "rome"),
            default="naples",
            multi=False)
    variant("craype-accel",
            values=("mi60", "mi100", "none"),
            default="none",
            multi=False)

    conflicts("craype-accel=mi60",
              when="craype-host=rome")

    conflicts("craype-accel=mi100",
              when="craype-host=naples")

    def install(self, spec, prefix):
        raise InstallError(
            self.spec.format('{name} is not installable, you need to specify '
                             'it as an external package in packages.yaml'))
