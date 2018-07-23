from distutils.core import setup

setup(
    name='Pyspectr',
    version='0.2.0',
    author='Nathan Brewer',
    author_email='brewer.nathant@gmail.com',
    packages=['Pyspectr'],
    url=['https://github.com/ntbrewer/Pyspectr'],
    scripts=['bin/py_grow_decay.py',
             'bin/spectrum_fitter.py','plotscatter.py'],
    license='LICENSE.txt',
    description='Useful spectroscopic tools',
    long_description=open('README.txt').read(),
    classifiers=[
        "Development Status :: 4 - Beta",
        "Intended Audience :: Science/Research",
        "License :: OSI Approved :: GNU General Public License v3 (GPLv3)",
        "Programming Language :: Python :: 3.3",
        "Topic :: Scientific/Engineering :: Physics",
    ],
    requires=['matplotlib', 'numpy', 'lmfit' , 'math' , 'sys' , 're' , 'tarfile' , 'struct' , 'os' , 'time'],
)
