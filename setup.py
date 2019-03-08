from setuptools import setup

setup(name='babies',
      version='0.2.1',
      description='Watch shows and record your viewing history',
      url='http://github.com/ohjames/babies',
      author='James Pike',
      author_email='github@chilon.net',
      license='MIT',
      scripts=['bin/babies'],
      packages=['babies'],
      install_requires=[
          'ruamel.yaml>=0.15.77',
          'python-mpv>=0.3.0',
          'readchar>=2.0.1',
      ],
      zip_safe=False)
