from setuptools import setup, find_packages

setup(
    name="gumroad-publisher",
    version="1.0.0",
    description="One-command Gumroad product build and publish pipeline",
    packages=find_packages(),
    python_requires=">=3.9",
    install_requires=[
        "requests>=2.31.0",
        "PyYAML>=6.0",
        "jinja2>=3.1.0",
        "urllib3>=2.0.0",
    ],
    entry_points={
        "console_scripts": [
            "gumroad-publish=gumroad_publisher.cli:main",
        ],
    },
)
