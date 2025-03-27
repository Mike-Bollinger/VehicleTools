from setuptools import setup, find_packages

setup(
    name="USBL_Nav_Smoother",
    version="0.1.0",
    author="Your Name",
    author_email="your.email@example.com",
    description="A tool for enhancing USBL navigation data using various smoothing algorithms.",
    long_description=open('README.md').read(),
    long_description_content_type="text/markdown",
    url="https://github.com/yourusername/USBL_Nav_Smoother",
    packages=find_packages(where='src'),
    package_dir={'': 'src'},
    install_requires=[
        "numpy",
        "pandas",
        "matplotlib",
        "geopy",
        "scikit-learn",
        "imageio",
        "shapely",
        "geopandas",
        "tkinter"
    ],
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
    ],
    python_requires='>=3.6',
)