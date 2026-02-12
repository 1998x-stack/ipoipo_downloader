from setuptools import setup, find_packages

setup(
    name="ipoipo-downloader",
    version="1.0.0",
    packages=find_packages(),
    install_requires=[
        "requests>=2.31.0",
        "fake-headers>=1.0.2",
        "loguru>=0.7.2",
        "PyYAML>=6.0.1",
        "beautifulsoup4>=4.12.2",
        "lxml>=4.9.3",
        "aiohttp>=3.9.1",
        "aiofiles>=23.2.1",
        "tqdm>=4.66.1"
    ],
    entry_points={
        'console_scripts': [
            'ipoipo-downloader=main:main',
        ],
    },
    author="Developer",
    description="Automated IPO Report Downloader with proxy support, resumable downloads, and smart deduplication",
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
    ],
    python_requires='>=3.8',
)