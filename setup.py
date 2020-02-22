import setuptools
from distutils.core import setup

with open("README.txt", "r") as fh:
    long_description = fh.read()

setuptools.setup(
    name='Pyspectr',
    version='0.2.3',
    author='Nathan Brewer',
    author_email='brewer.nathant@gmail.com',
    packages=setuptools.find_packages(),
    url='https://github.com/ntbrewer/Pyspectr',
    scripts=['bin/py_grow_decay.py', 'bin/spectrum_fitter.py' , 'bin/plotscatter.py',],
    license='LICENSE.txt',
    description='Useful spectroscopic tools',
    long_description=long_description,
    long_description_content_type="text/markdown",
    classifiers=(
        "Development Status :: 5 - Production/Stable",
        "Intended Audience :: Science/Research",
        "License :: OSI Approved :: GNU General Public License v3 (GPLv3)",
        "Programming Language :: Python :: 3.5",
        "Topic :: Scientific/Engineering :: Physics",
    ),
    requires=['matplotlib', 'numpy', 'lmfit'],
)
