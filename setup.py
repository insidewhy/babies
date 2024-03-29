from setuptools import setup

setup(
    name="babies",
    version="0.2.1",
    description="Watch shows and record your viewing history",
    url="http://github.com/insidewhy/babies",
    author="James Pike",
    author_email="github@chilon.net",
    license="MIT",
    scripts=["bin/babies"],
    packages=["babies"],
    install_requires=[
        "ruamel.yaml>=0.15.77",
        "python-mpv>=0.5.0",
        "readchar>=2.0.1",
        "ffmpeg",
        "mypy-extensions",
    ],
    tests_requires=["mypy>=0.711"],
    zip_safe=False,
)
