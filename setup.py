from setuptools import setup

setup(name='Show',
      version='0.2',
      description='Watch shows and record your viewing history',
      url='http://github.com/ohjames/Show',
      author='James Pike',
      author_email='github@chilon.net',
      license='MIT',
      scripts=['bin/Show'],
      packages=['libshow'],
      install_requires=[
          'ruamel.yaml>=0.15.77',
          'python-mpv>=0.3.0'
      ],
      zip_safe=False)
