from setuptools import setup, find_packages

setup(
    name="glean",
    version="0.1.0a0",
    description="Tools for processing results of the Climate Prospectus.",
    url="https://github.com/ClimateImpactLab/glean",
    author="James Rising",
    author_email="jarising@gmail.com",
    license="MIT",
    packages=find_packages(),
    install_requires=["click", "pyyaml", "numpy", "scipy", "statsmodels", "netCDF4"],
    extras_require={
        "test": ["pytest"],
        "dev": ["pytest", "pytest-cov", "wheel", "flake8", "black", "twine"],
    },
    entry_points="""
    [console_scripts]
    glean=glean.cli:glean_cli
""",
)