from setuptools import setup

setup(name='Show',
      version='0.1',
      description='Watch shows and record your viewing history',
      url='http://github.com/ohjames/Show',
      author='James Pike',
      author_email='github@chilon.net',
      license='MIT',
      scripts=['bin/Show'],
      packages=['libshow'],
      zip_safe=False)
